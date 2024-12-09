from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from .models import Event, UserProfile, UserThread, ChatMessage, ChatSession, Conversation
from .forms import UserProfileForm, EventForm
from dotenv import load_dotenv
import json
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)

# Load environment variables
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
        if current_phase == 'factual_description':
            event.current_phase = 'emotional_response'
        elif current_phase == 'emotional_response':
            event.current_phase = 'behavioral_associations'
        elif current_phase == 'behavioral_associations':
            event.current_phase = 'positive_reframing'
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
            event_id = data.get('event_id')
            phase = data.get('phase')
            
            logger.info(f"Received request data: message={message}, event_id={event_id}, phase={phase}")
            
            if not message:
                logger.warning("No message provided in request")
                return JsonResponse({'error': 'No message provided'})
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON request: {str(e)}")
            return JsonResponse({'error': 'Invalid request format'})

        try:
            user_profile = UserProfile.objects.get(user=request.user)
            logger.info(f"Got user profile for {request.user.username}")
            
            system_prompt = get_personality_instructions(user_profile.personality_preference)
            logger.info("Generated system prompt")
            
            user_context = get_user_context(request.user)
            if user_context:
                system_prompt += f"\n\nUser Context:\n{user_context}"
            
            # Get the event if event_id is provided, otherwise get the latest event
            if event_id:
                current_event = get_object_or_404(Event, id=event_id, user=request.user)
                logger.info(f"Found event with id {event_id}")
            else:
                current_event = Event.objects.filter(user=request.user).order_by('-created_at').first()
                logger.info("Using latest event")
            
        except UserProfile.DoesNotExist:
            logger.error(f"UserProfile not found for user {request.user.username}")
            return JsonResponse({'error': 'User profile not found'})
        except Event.DoesNotExist:
            logger.error(f"Event not found: {event_id}")
            return JsonResponse({'error': 'Event not found'})
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}", exc_info=True)
            return JsonResponse({'error': 'Failed to get user context'})

        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if current_event:
            messages[0]["content"] += f"\n\nCurrent Event: {current_event.title}"
            messages[0]["content"] += f"\nCurrent Phase: {phase or current_event.current_phase}"
            
            # Get previous messages for this event and phase
            previous_messages = ChatMessage.objects.filter(
                user_thread__user=request.user,
                user_thread__event=current_event,
                phase=phase or current_event.current_phase
            ).order_by('created_at')[:5]
            
            for prev_msg in previous_messages:
                messages.append({
                    "role": "user" if prev_msg.message_type == "user" else "assistant",
                    "content": prev_msg.content
                })
        
        messages.append({"role": "user", "content": message})
        
        logger.info(f"Sending request to OpenAI with {len(messages)} messages")
        
        try:
            logger.info("Attempting to call OpenAI API")
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            logger.info("Successfully received OpenAI API response")
            
            assistant_message = response.choices[0].message.content
            logger.info("Extracted assistant message")

            # Save messages to database
            if current_event:
                logger.info("Getting/creating user thread")
                # Get the latest thread or create a new one
                try:
                    user_thread = UserThread.objects.filter(
                        user=request.user,
                        event=current_event
                    ).latest('created_at')
                    created = False
                except UserThread.DoesNotExist:
                    user_thread = UserThread.objects.create(
                        user=request.user,
                        event=current_event,
                        thread_id=str(uuid.uuid4())
                    )
                    created = True
                
                logger.info(f"{'Created new' if created else 'Using existing'} user thread")
                
                logger.info("Saving user message")
                ChatMessage.objects.create(
                    user_thread=user_thread,
                    content=message,
                    message_type='user',
                    phase=phase or current_event.current_phase
                )
                
                logger.info("Saving assistant message")
                ChatMessage.objects.create(
                    user_thread=user_thread,
                    content=assistant_message,
                    message_type='assistant',
                    phase=phase or current_event.current_phase
                )
                
                # Check for phase progression
                if check_phase_progression(assistant_message, current_event):
                    logger.info(f"Phase progressed for event {current_event.id}")
            
            logger.info("Sending response back to client")
            return JsonResponse({'response': assistant_message})
            
        except Exception as e:
            logger.error(f"Error in OpenAI communication: {str(e)}", exc_info=True)
            return JsonResponse({'error': str(e)})
            
    except Exception as e:
        logger.error(f"Error in get_chatbot_response: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Failed to get AI response'})

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
    
    # Get chat sessions for the current phase
    sessions = ChatSession.objects.filter(
        event=event,
        phase=event.current_phase
    ).order_by('-timestamp')
    
    logger.info(f"Event detail - Found {sessions.count()} sessions for event {event_id}, phase {event.current_phase}")
    for session in sessions:
        logger.info(f"Session {session.id}: {session.title} ({session.phase})")
    
    return render(request, 'chatbot/event_detail.html', {
        'event': event,
        'sessions': sessions,
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
        'factual_description': "Let's focus on describing the factual details of this event. What happened? When? Where? Who was involved?",
        'emotional_response': "Now, let's explore your emotional response to this event. How did you feel during and after?",
        'behavioral_associations': "Let's examine your thoughts and behaviors associated with this event. What patterns do you notice?",
        'positive_reframing': "Finally, let's reflect on personal growth. How has this experience shaped you? What strengths or insights have you gained?"
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
        
        # Redirect to chat with event_id
        return redirect(f'/chat/?event_id={event_id}')
        
    except Exception as e:
        logger.error(f"Error starting writing session: {str(e)}", exc_info=True)
        messages.error(request, "Failed to start writing session. Please try again.")
        return redirect('event_detail', event_id=event.id)

@login_required
def chat(request):
    if request.method == 'GET':
        event_id = request.GET.get('event_id')
        if event_id:
            event = get_object_or_404(Event, id=event_id, user=request.user)
            return render(request, 'chatbot/home.html', {'event': event})
        else:
            # If no event_id is provided, show the general chat interface
            conversations = []
            if request.user.is_authenticated:
                conversations = Conversation.objects.filter(user=request.user).order_by('-updated_at')
            return render(request, 'chatbot/home.html', {'event': None, 'conversations': conversations})
    elif request.method == 'POST':
        try:
            logger.info("Chat POST request received")
            # We don't need to parse the request body here since get_chatbot_response does that
            return get_chatbot_response(request)
            
        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
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
def get_phase_sessions(request, event_id, phase):
    """API endpoint to get chat sessions for a specific phase"""
    try:
        logger.info(f"API - Fetching sessions for event {event_id}, phase {phase}")
        
        # Validate the event exists and belongs to the user
        event = get_object_or_404(Event, id=event_id, user=request.user)
        logger.info(f"Found event: {event}")
        
        # Validate the phase is valid
        if phase not in dict(Event.WRITING_PHASE_CHOICES):
            logger.error(f"Invalid phase: {phase}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid writing phase'
            }, status=400)
        
        # Get all sessions for this event and phase
        sessions = ChatSession.objects.filter(
            event=event,
            phase=phase
        ).order_by('-timestamp')
        logger.info(f"API - Found {sessions.count()} sessions")
        
        # Log each session for debugging
        for session in sessions:
            logger.info(f"Session {session.id}: {session.title} ({session.phase})")
        
        # Format the session data
        sessions_data = []
        for session in sessions:
            try:
                session_data = {
                    'id': session.id,
                    'title': session.title or f"Session from {session.timestamp.strftime('%B %d, %Y')}",
                    'formatted_date': session.get_formatted_date(),
                }
                sessions_data.append(session_data)
            except Exception as e:
                logger.error(f"Error formatting session {session.id}: {str(e)}", exc_info=True)
                continue
        
        return JsonResponse({
            'success': True,
            'sessions': sessions_data
        })
        
    except Event.DoesNotExist:
        logger.error(f"Event not found: {event_id}")
        return JsonResponse({
            'success': False,
            'error': 'Event not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error fetching phase sessions: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f"Error loading sessions: {str(e)}"
        }, status=500)

@login_required
def save_session(request):
    try:
        logger.info("Starting save_session")
        
        # Parse and validate request data
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Parsed data: {data}")
            
            if not isinstance(data.get('messages'), list):
                logger.error("Messages is not a list")
                raise ValueError("Messages must be a list")
            
            # Validate required fields
            required_fields = ['event_id', 'phase', 'messages']
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    raise KeyError(f"Missing required field: {field}")
            
            # Validate message format
            for msg in data['messages']:
                if not all(key in msg for key in ['content', 'type']):
                    logger.error("Invalid message format")
                    raise ValueError("Invalid message format - must have content and type")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Invalid JSON format'})
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            return JsonResponse({'success': False, 'error': str(e)})
        
        # Get event and verify ownership
        try:
            event = Event.objects.get(id=data['event_id'], user=request.user)
            logger.info(f"Found event: {event}")
        except Event.DoesNotExist:
            logger.error(f"Event not found. User: {request.user}, Event ID: {data.get('event_id')}")
            return JsonResponse({'success': False, 'error': 'Event not found'})
        
        # Generate a title based on the first message or use provided title
        title = data.get('title', '')
        if not title and data['messages']:
            # Use the first user message as the title, truncated
            user_messages = [msg for msg in data['messages'] if msg['type'] == 'user']
            if user_messages:
                title = user_messages[0]['content'][:100] + ('...' if len(user_messages[0]['content']) > 100 else '')
            else:
                title = f"{event.title} - {data['phase']} Session"
        
        # Create a new session
        logger.info(f"Creating new session for phase: {data['phase']}")
        session = ChatSession.objects.create(
            event=event,
            phase=data['phase'],
            title=title
        )
        
        # Save messages
        logger.info(f"Saving {len(data['messages'])} messages")
        session.set_messages(data['messages'])
        session.save()
        logger.info(f"Session saved successfully with ID: {session.id}")
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'title': session.title
        })
        
    except Exception as e:
        logger.error(f"Error saving chat session: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def view_session(request, session_id):
    """View a specific chat session"""
    try:
        # Get the session and verify ownership
        session = get_object_or_404(ChatSession, id=session_id)
        if session.event.user != request.user:
            logger.warning(f"User {request.user} attempted to access session {session_id} belonging to {session.event.user}")
            raise Http404("Session not found")
        
        # Get the messages from the session
        messages = session.get_messages()
        
        return render(request, 'chatbot/session_detail.html', {
            'session': session,
            'messages': messages,
            'event': session.event
        })
        
    except Exception as e:
        logger.error(f"Error viewing session {session_id}: {str(e)}", exc_info=True)
        messages.error(request, "Error loading session")
        return redirect('event_detail', event_id=session.event.id)
