# ReflectionApp

## Overview

This is a web application designed to facilitate structured reflective learning through guided conversations. The application helps learners reflect on a specific learning experience by asking a series of carefully crafted questions that prompt deep, meaningful responses.

## Features

1. Multi-language support (English, German, Spanish, Estonian)
2. Guided reflection process with three key questions:
   - What happened and what did you do to resolve the issue?
   - What were the reasons for these issues?
   - What have you learned from this for the future?
3. Intelligent response classification using OpenAI's GPT-5.2
4. Dynamic follow-up questions based on incomplete or unclear responses (up to 2 follow-ups per question)
5. Conversation tracking and database storage
6. Conversation download functionality
7. Session management with ability to pause and resume
8. Robust error handling with graceful fallback on LLM failures

## Technology Stack

- **Backend:** Flask 3.1
- **Database:** SQLAlchemy 2.0 with SQLite
- **AI Model:** OpenAI GPT-5.2 via LangChain 1.2 (LCEL)
- **Language Support:** Multilingual (EN, DE, ES, ET)
- **Deployment:** Gunicorn 25 + nginx (Unix socket)
- **Key Libraries:** langchain, langchain-openai, pytz, python-dotenv

## Prerequisites

- Python 3.12+
- OpenAI API Key
- Required Python packages (see `requirements.txt`)

## Installation

```bash
# Clone the repository
git clone https://github.com/gertipishtari/ReflectionApp.git
cd ReflectionApp

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=your-api-key-here
FLASK_SECRET_KEY=your-secret-key-here
EOF

# Run the application
python app.py
```

## Production Deployment

The application is deployed with Gunicorn behind nginx:

```bash
gunicorn --preload --workers 3 --bind unix:totbot.sock -m 007 app:app
```

## Project Structure

```
ReflectionApp/
├── app.py
├── requirements.txt
├── static/
│   ├── app.js
│   └── styles.css
└── templates/
    └── index.html
```

## License

CC0-1.0
