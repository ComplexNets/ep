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
def get_or_create_assistant():
    """Get existing assistant or create a new one"""
    try:
        assistants = client.beta.assistants.list(
            order="desc",
            limit=1,
        )
        
        # Return existing assistant if found
        if len(assistants.data) > 0:
            return assistants.data[0]
            
        # Create new assistant if none exists
        assistant = client.beta.assistants.create(
            name="Expressive Writing Coach",
            instructions="""You are an empathetic writing coach specializing in expressive writing. 
            Guide users through emotional exploration and self-reflection through writing.
            Create a safe space for users to express themselves freely.
            Ask thoughtful questions that help users dig deeper into their feelings and experiences.
            Maintain a supportive and understanding presence throughout the conversation.""",
            model=os.getenv('OPENAI_MODEL', "gpt-4-0125-preview"),
            tools=[{"type": "code_interpreter"}]  
        )
        return assistant
        
    except Exception as e:
        print(f"Error creating assistant: {str(e)}")
        raise

# Initialize the assistant
ASSISTANT = get_or_create_assistant()

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

def get_chatbot_response(message, user):
    try:
        # Get or create user's thread
        user_thread = get_or_create_thread(user)
        
        # Get user context
        user_context = get_user_context(user)
        
        # If this is a new thread or if context exists, send the context first
        if user_context:
            client.beta.threads.messages.create(
                thread_id=user_thread.thread_id,
                role="user",
                content=f"Important context for our conversation: {user_context}"
            )

        # Add the user's message to the thread
        client.beta.threads.messages.create(
            thread_id=user_thread.thread_id,
            role="user",
            content=message
        )

        # Run the assistant
        run = client.beta.threads.runs.create(
            thread_id=user_thread.thread_id,
            assistant_id=ASSISTANT.id,
            instructions="""You are an empathetic writing coach specializing in expressive writing. Your role is to:
            1. Create a safe, non-judgmental space for emotional expression
            2. Ask thoughtful questions that help users explore their feelings deeper
            3. Encourage detailed, specific writing rather than general statements
            4. Help users identify and articulate their emotions
            5. Provide gentle guidance while letting users lead their own emotional journey
            6. Maintain a supportive and encouraging tone throughout the conversation
            
            Keep responses concise but meaningful, and always maintain a warm, understanding presence.
            Use any provided user context to personalize your responses and guidance."""
        )

        # Wait for the response
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=user_thread.thread_id,
                run_id=run.id
            )
            if run_status.status == 'completed':
                break
            elif run_status.status == 'failed':
                return "I apologize, but I encountered an error. Please try again."
            time.sleep(0.5)

        # Get the assistant's response
        messages = client.beta.threads.messages.list(
            thread_id=user_thread.thread_id,
            order="desc",
            limit=1
        )
        
        # Update last interaction time
        user_thread.save()  # This updates last_interaction due to auto_now=True
        
        # Get the latest assistant message
        for msg in messages.data:
            if msg.role == "assistant":
                return msg.content[0].text.value
                
        return "I apologize, but I couldn't generate a response. Please try again."

    except Exception as e:
        return str(e)

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
        'associations': "Let's connect this experience to your current behaviors and patterns. How do you see this event influencing your present life?"
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
@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            bot_response = get_chatbot_response(user_message, request.user)
            return JsonResponse({'response': bot_response})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
