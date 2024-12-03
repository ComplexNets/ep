from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import json
from django.conf import settings
import os
from dotenv import load_dotenv
import time
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserThread, UserProfile, Event, Conversation, ChatMessage, ChatSession
from .forms import UserProfileForm, EventForm
from django.utils import timezone
import logging
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_personality_instructions(personality):
    base_instructions = """Your role is to guide users through four distinct writing phases:
            
1. Factual Description: Help users objectively describe what happened, focusing on the concrete details.
2. Emotional Response: Guide users to explore and express their feelings about the event.
3. Behavioral Associations: Help users connect the event to their behaviors, patterns, and potential future actions.
4. Positive Reframing & Growth: Guide users to:
   - Identify positive aspects or potential benefits from the experience
   - Reflect on personal growth and lessons learned
   - Set goals or action steps for future improvement
   - Find meaning or purpose in their experience

For each phase:
- Guide users with appropriate prompts and questions for that specific phase
- Evaluate when they've adequately completed the current phase
- When you feel they're ready to move to the next phase, respond with: "PHASE_COMPLETE: [current_phase]"
"""
    
    personality_styles = {
        'friendly': """Maintain a warm, casual, and approachable tone. Use informal language, 
        share occasional light-hearted comments, and make the writing process feel fun and engaging. 
        Feel free to use encouraging emojis and conversational phrases.""",
        
        'professional': """Maintain a formal, academic tone. Use precise language and professional terminology. 
        Focus on structured analysis and methodical progression through the writing phases. 
        Provide clear, well-organized guidance with academic references when relevant.""",
        
        'encouraging': """Be highly motivational and energetic. Celebrate small wins, provide frequent positive reinforcement, 
        and maintain an upbeat, supportive tone throughout the conversation. Focus on building confidence 
        and maintaining momentum."""
    }
    
    return f"{base_instructions}\n\nTone and Style:\n{personality_styles.get(personality, personality_styles['friendly'])}"

def get_user_context(user):
    """Get user's biographical context and writing goals"""
    try:
        profile = UserProfile.objects.get(user=user)
        context = []
        if profile.bio_context:
            context.append(f"Bio: {profile.bio_context}")
        if profile.writing_goals:
            context.append(f"Writing Goals: {profile.writing_goals}")
        return "\n".join(context) if context else None
    except UserProfile.DoesNotExist:
        return None

def check_phase_progression(message_content, event):
    """Check if the AI has indicated phase completion and update accordingly"""
    if "PHASE_COMPLETE:" in message_content:
        current_phase = event.current_phase
        if current_phase == 'facts':
            event.current_phase = 'feelings'
        elif current_phase == 'feelings':
            event.current_phase = 'associations'
        elif current_phase == 'associations':
            event.current_phase = 'growth'
        event.save()
        return True
    return False

@login_required
def get_chatbot_response(request):
    try:
        logger.info("Starting get_chatbot_response")
        try:
            data = json.loads(request.body)
            message = data.get('message')
            if not message:
                logger.warning("No message provided in request")
                return JsonResponse({'error': 'No message provided'})
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON request: {str(e)}")
            return JsonResponse({'error': 'Invalid request format'})

        try:
            user_profile = UserProfile.objects.get(user=request.user)
            system_prompt = get_personality_instructions(user_profile.personality_preference)
            
            user_context = get_user_context(request.user)
            if user_context:
                system_prompt += f"\n\nUser Context:\n{user_context}"
            
            current_event = Event.objects.filter(user=request.user).order_by('-created_at').first()
            
        except UserProfile.DoesNotExist:
            logger.error(f"UserProfile not found for user {request.user.username}")
            return JsonResponse({'error': 'User profile not found'})
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to get user context'})

        try:
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            if current_event:
                messages[0]["content"] += f"\n\nCurrent Event: {current_event.title}"
                messages[0]["content"] += f"\nCurrent Phase: {current_event.current_phase}"
                
                previous_messages = ChatMessage.objects.filter(
                    user_thread__user=request.user,
                    user_thread__event=current_event
                ).order_by('created_at')[:5]
                
                for prev_msg in previous_messages:
                    messages.append({
                        "role": "user" if prev_msg.message_type == "user" else "assistant",
                        "content": prev_msg.content
                    })
            
            messages.append({"role": "user", "content": message})
            
            logger.info(f"Sending request to OpenAI with {len(messages)} messages")
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            assistant_message = response.choices[0].message.content
            logger.info("Received response from OpenAI")
            
        except Exception as e:
            logger.error(f"Error in OpenAI communication: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to get AI response'})

        try:
            # Get the latest UserThread or create a new one
            user_thread = UserThread.objects.filter(
                user=request.user,
                event=current_event
            ).order_by('-created_at').first()
            
            if not user_thread:
                user_thread = UserThread.objects.create(
                    user=request.user,
                    event=current_event,
                    thread_id=str(timezone.now().timestamp())
                )
            
            if current_event:
                if check_phase_progression(assistant_message, current_event):
                    assistant_message = assistant_message.replace(f"PHASE_COMPLETE: {current_event.current_phase}", "")
                    assistant_message += f"\n\nGreat progress! Let's move on to the {current_event.get_current_phase_display()} phase."
            
            ChatMessage.objects.create(
                user_thread=user_thread,
                event=current_event,
                content=message,
                message_type='user'
            )
            
            ChatMessage.objects.create(
                user_thread=user_thread,
                event=current_event,
                content=assistant_message,
                message_type='assistant'
            )
            
            return JsonResponse({'response': assistant_message})
            
        except Exception as e:
            logger.error(f"Error saving chat messages: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to save chat messages'})
            
    except Exception as e:
        logger.error(f"Unexpected error in get_chatbot_response: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)})

@login_required
def home(request):
    conversations = []
    if request.user.is_authenticated:
        conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')
    return render(request, 'chatbot/home.html', {'conversations': conversations})

@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'chatbot/profile.html', {'form': form})

@login_required
def event_list(request):
    events = Event.objects.filter(user=request.user)
    return render(request, 'chatbot/event_list.html', {'events': events})

@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user
            event.save()
            messages.success(request, 'Event created successfully.')
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm()
    
    return render(request, 'chatbot/event_form.html', {'form': form, 'action': 'Create'})

@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    
    threads = UserThread.objects.filter(event=event).order_by('-created_at')
    
    for thread in threads:
        thread.messages = thread.chatmessage_set.all().order_by('created_at')
    
    return render(request, 'chatbot/event_detail.html', {
        'event': event,
        'threads': threads,
    })

@login_required
def event_update(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('event_detail', event_id=event.id)
    else:
        form = EventForm(instance=event)
    
    return render(request, 'chatbot/event_form.html', {'form': form, 'action': 'Update'})

@login_required
def event_delete(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event was successfully deleted.')
        return redirect('event_list')
    return redirect('event_detail', event_id=event_id)

@login_required
def start_writing_session(request, event_id):
    event = get_object_or_404(Event, id=event_id, user=request.user)
    
    # Create a new thread for this writing session
    user_thread = UserThread.objects.create(
        user=request.user,
        event=event,
        thread_id=str(timezone.now().timestamp())
    )
    
    # Add initial context message
    phase_prompts = {
        'facts': "Let's focus on describing the factual details of this event. What happened? When? Where? Who was involved?",
        'feelings': "Now, let's explore your emotional response to this event. How did you feel during and after?",
        'thoughts': "Let's examine your thoughts and beliefs about this event. What did you learn? How did it change your perspective?",
        'growth': "Finally, let's reflect on personal growth. How has this experience shaped you? What strengths or insights have you gained?"
    }
    
    initial_prompt = phase_prompts.get(event.current_phase, "Let's begin your writing session.")
    
    # Get user profile and context
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        system_prompt = get_personality_instructions(user_profile.personality_preference)
        
        # Add user context
        user_context = get_user_context(request.user)
        if user_context:
            system_prompt += f"\n\nUser Context:\n{user_context}"
            
        # Add event context
        system_prompt += f"\n\nCurrent Event: {event.title}"
        system_prompt += f"\nCurrent Phase: {event.current_phase}"
        
        # Get initial response from OpenAI
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": initial_prompt}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        assistant_message = response.choices[0].message.content
        
        # Save the initial message
        ChatMessage.objects.create(
            user_thread=user_thread,
            event=event,
            content=assistant_message,
            message_type='assistant'
        )
        
        return redirect('chat')
        
    except Exception as e:
        logger.error(f"Error starting writing session: {str(e)}", exc_info=True)
        messages.error(request, "Failed to start writing session. Please try again.")
        return redirect('event_detail', event_id=event.id)

@login_required
def chat(request):
    if request.method == 'GET':
        return render(request, 'chatbot/home.html')
    elif request.method == 'POST':
        try:
            print("Chat POST request received")  # Debug log
            data = json.loads(request.body)
            user_message = data.get('message', '')
            print(f"Processing message: {user_message}")  # Debug log
            
            if not user_message:
                return JsonResponse({'error': 'No message provided'}, status=400)
            
            bot_response = get_openai_response(user_message, get_or_create_thread(request.user))
            print(f"Bot response: {bot_response}")  # Debug log
            return JsonResponse({'message': bot_response})
            
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")  # Debug log
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Chat error: {str(e)}")  # Debug log
            return JsonResponse({'error': 'An error occurred processing your request'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def get_conversation(request, conversation_id):
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = ChatMessage.objects.filter(event=conversation.event).order_by('created_at')
        
        messages_data = [{
            'content': msg.content,
            'message_type': msg.message_type,
            'timestamp': msg.created_at.isoformat()
        } for msg in messages]
        
        return JsonResponse({
            'id': conversation.id,
            'title': conversation.title,
            'messages': messages_data
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    except Exception as e:
        logger.error(f'Error in get_conversation: {str(e)}')
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def get_phase_history(request, event_id, phase):
    try:
        event = get_object_or_404(Event, id=event_id, user=request.user)
        thread = UserThread.objects.filter(event=event).first()
        
        if not thread:
            return JsonResponse({'messages': []})
            
        messages = ChatMessage.objects.filter(
            user_thread=thread,
            phase=phase
        ).order_by('created_at')
        
        messages_data = []
        for msg in messages:
            messages_data.append({
                'content': msg.content,
                'type': msg.message_type,
                'timestamp': msg.created_at.strftime('%Y-%m-%d %H:%M')
            })
            
        return JsonResponse({
            'messages': messages_data,
            'phase': phase,
            'phase_display': dict(Event.PHASE_CHOICES)[phase]
        })
    except Exception as e:
        logger.error(f"Error getting phase history: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def save_session(request):
    try:
        data = json.loads(request.body)
        event = Event.objects.get(id=data['event_id'])
        
        session = ChatSession(
            event=event,
            phase=data['phase']
        )
        session.set_messages(data['messages'])
        session.save()
        
        return JsonResponse({'success': True})
    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Event not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
