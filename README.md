**ReflectionApp**

**Overview**

This is a web application designed to facilitate structured reflective learning through guided conversations. The application helps learners reflect on a specific learning experience by asking a series of carefully crafted questions that prompt deep, meaningful responses.

**Features**

1. Multi-language support (English, German, Spanish, Estonian)

2. Guided reflection process with three key questions:

- What happened and what did you do to resolve the issue?
- What were the reasons for these issues?
- What have you learned from this for the future?


3. Intelligent response classification using OpenAI's GPT-4o
4. Dynamic follow-up questions based on incomplete or unclear responses
5. Conversation tracking and database storage
6. Conversation download functionality
7. Session management with ability to pause and resume

**Technology Stack**

- Backend: Flask
- Database: SQLAlchemy with SQLite
- AI Model: OpenAI GPT-4o
- Language Support: Multilingual
- Libraries: langchain, pytz, python-dotenv

**Prerequisites**

- Python 3.8+
- OpenAI API Key
- Flask
- Required Python packages (see _requirements.txt_)
