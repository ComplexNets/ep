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
from .models import UserThread, UserProfile, Event
from .forms import UserProfileForm, EventForm

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create or get the assistant
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
        and help users see their potential. Use inspiring language and focus on progress and achievement.""",
        
        'empathetic': """Be gentle, understanding, and deeply supportive. Acknowledge emotions with sensitivity, 
        validate feelings, and create a safe space for expression. Use compassionate language and show deep understanding 
        of the user's experiences."""
    }
    
    return f"{base_instructions}\n\nTone and Style:\n{personality_styles.get(personality, personality_styles['friendly'])}"

def get_or_create_assistant(personality):
    try:
        # Set a high token limit for long writing sessions
        model = "gpt-4-0125-preview"  # Latest model with 128k context window
        
        instructions = get_personality_instructions(personality)
        
        # Create a new assistant with high token limits
        assistant = client.beta.assistants.create(
            name="Expressive Writing Guide",
            instructions=instructions,
            model=model,
            tools=[],
        )
        return assistant
    except Exception as e:
        print(f"Error creating assistant: {str(e)}")
        return None

def get_or_create_thread(user):
    """Get existing thread or create a new one for the user"""
    user_thread = UserThread.objects.filter(user=user).order_by('-last_interaction').first()
    
    if not user_thread:
        # Create a new thread
        thread = client.beta.threads.create()
        user_thread = UserThread.objects.create(
            user=user,
            thread_id=thread.id
        )
    return user_thread

def get_user_context(user):
    """Get user's biographical context and writing goals"""
    profile, created = UserProfile.objects.get_or_create(user=user)
    context = "User Context:\n"
    
    if profile.bio_context:
        context += f"Background: {profile.bio_context}\n"
    if profile.writing_goals:
        context += f"Writing Goals: {profile.writing_goals}\n"
    
    return context if len(context) > 14 else None  # Return None if no real context added

def check_phase_progression(message_content, event, user_thread):
    """Check if the AI has indicated phase completion and update accordingly"""
    if "PHASE_COMPLETE:" in message_content:
        current_phase = event.current_phase
        phase_mapping = {
            'facts': 'feelings',
            'feelings': 'associations',
            'associations': 'growth',
            'growth': 'growth'  # Stay in final phase
        }
        
        # Update to next phase
        next_phase = phase_mapping[current_phase]
        event.current_phase = next_phase
        event.save()
        
        # Create new thread for next phase
        new_thread = client.beta.threads.create()
        user_thread.thread_id = new_thread.id
        user_thread.writing_phase = next_phase
        user_thread.save()
        
        return True
    return False

def get_chatbot_response(message, user):
    try:
        # Get or create user's thread
        user_thread = get_or_create_thread(user)
        
        # Get the associated event
        event = user_thread.event
        
        # Get user context
        user_context = get_user_context(user)
        
        # Get user's personality preference
        user_profile = UserProfile.objects.get(user=user)
        personality = user_profile.personality_preference
        
        # Create a new assistant with the user's preferred personality
        assistant = get_or_create_assistant(personality)
        if not assistant:
            return "I apologize, but I encountered an error. Please try again."
        
        # Add the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=user_thread.thread_id,
            role="user",
            content=message
        )

        # Run the assistant with a longer timeout
        run = client.beta.threads.runs.create(
            thread_id=user_thread.thread_id,
            assistant_id=assistant.id,
            instructions="""Remember that expressive writing sessions can be long (up to 20 minutes). 
            Do not interrupt the user while they are writing. Only respond when they explicitly ask for guidance 
            or when they indicate they are done with their current writing. Focus on encouraging deep, 
            continuous writing rather than frequent back-and-forth dialogue."""
        )

        # Wait for completion with a longer timeout
        timeout = 60  # 60 seconds timeout
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                return "I apologize, but the response is taking longer than expected. Please try again."
                
            run_status = client.beta.threads.runs.retrieve(
                thread_id=user_thread.thread_id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                return "I apologize, but I encountered an error. Please try again."
            time.sleep(1)

        # Get the assistant's messages
        messages = client.beta.threads.messages.list(
            thread_id=user_thread.thread_id
        )
        
        # Get the latest assistant message
        assistant_message = messages.data[0].content[0].text.value
        
        # Check for phase progression
        if event and check_phase_progression(assistant_message, event, user_thread):
            # Remove the PHASE_COMPLETE marker from the message
            assistant_message = assistant_message.replace("PHASE_COMPLETE: " + event.current_phase, "")
            assistant_message += f"\n\nGreat progress! Let's move on to the {event.get_current_phase_display()} phase."
        
        # Update last interaction time
        user_thread.save()
        
        return assistant_message

    except Exception as e:
        print(f"Error getting chatbot response: {str(e)}")
        return "I apologize, but I encountered an error. Please try again."

@login_required
def home(request):
    return render(request, 'chatbot/home.html')

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
    thread = client.beta.threads.create()
    user_thread = UserThread.objects.create(
        user=request.user,
        event=event,
        thread_id=thread.id,
        writing_phase=event.current_phase
    )
    
    # Add initial context message
    phase_prompts = {
        'facts': "Let's focus on describing the factual details of this event. What happened? When? Where? Who was involved?",
        'feelings': "Now, let's explore your emotional response to this event. How did you feel during and after?",
        'associations': "Let's connect this experience to your current behaviors and patterns. How do you see this event influencing your present life?",
        'growth': "Let's focus on finding positive aspects and growth opportunities from this experience. What did you learn? How can you apply this to your life?"
    }
    
    initial_message = (
        f"Event: {event.title}\n"
        f"Phase: {event.get_current_phase_display()}\n\n"
        f"{phase_prompts[event.current_phase]}"
    )
    
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=initial_message
    )
    
    return redirect('home')

@login_required
def chat(request):
    if request.method == 'GET':
        return render(request, 'chatbot/home.html')
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            bot_response = get_chatbot_response(user_message, request.user)
            return JsonResponse({'message': bot_response})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Chat error: {str(e)}")  # Log the error
            return JsonResponse({'error': 'An error occurred processing your request'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
