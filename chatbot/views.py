from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import json
from django.conf import settings
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_chatbot_response(message):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are an empathetic writing coach specializing in expressive writing. Your role is to:
                1. Create a safe, non-judgmental space for emotional expression
                2. Ask thoughtful questions that help users explore their feelings deeper
                3. Encourage detailed, specific writing rather than general statements
                4. Help users identify and articulate their emotions
                5. Provide gentle guidance while letting users lead their own emotional journey
                6. Maintain a supportive and encouraging tone throughout the conversation

                Keep responses concise but meaningful, and always maintain a warm, understanding presence."""},
                {"role": "user", "content": message}
            ],
            max_tokens=250,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return str(e)

def home(request):
    return render(request, 'chatbot/home.html')

@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            bot_response = get_chatbot_response(user_message)
            return JsonResponse({'response': bot_response})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
