# Expressive Writing Chatbot

A Django-based web application featuring an AI-powered chatbot designed to guide users through expressive writing exercises. The chatbot uses OpenAI's GPT-3.5-turbo model to provide empathetic and supportive guidance for emotional expression and self-reflection.

## Features

- Real-time chat interface
- OpenAI GPT-3.5-turbo integration
- Responsive and modern UI
- Supportive writing coach functionality

## Setup

1. Clone the repository:
```bash
git clone https://github.com/ComplexNets/ep.git
cd ep
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a .env file in the project root and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Start the development server:
```bash
python manage.py runserver
```

Visit http://127.0.0.1:8000/ to start using the chatbot.

## Technology Stack

- Django 4.2+
- OpenAI API
- HTML/CSS/JavaScript
- Python 3.8+
