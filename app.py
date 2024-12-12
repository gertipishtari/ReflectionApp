from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import JSON
from datetime import datetime
import pytz
import uuid
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json
import re
import logging

logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Database models (unchanged logic)
# ---------------------------------------------------------------------------

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(2), nullable=False)
    conversation_status = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    json_data = db.Column(JSON, nullable=False)
    responses = db.relationship('Response', backref='student', lazy=True)

class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    question_number = db.Column(db.Integer, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    final_unmet_criteria = db.Column(JSON, nullable=False)
    attempts = db.relationship('Attempt', backref='response', lazy=True)

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey('response.id'), nullable=False)
    attempt_number = db.Column(db.Integer, nullable=False)
    response_type = db.Column(db.String(20), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    unmet_criteria = db.Column(JSON, nullable=False)
    classifications = db.relationship('Classification', backref='attempt', lazy=True)

class Classification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('attempt.id'), nullable=False)
    criterion = db.Column(db.String(255), nullable=False)
    is_met = db.Column(db.Boolean, nullable=False)

# ---------------------------------------------------------------------------
# LLM setup – using modern LangChain LCEL (no deprecated LLMChain)
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm_classifier = ChatOpenAI(temperature=0.0, model="gpt-5.2", api_key=OPENAI_API_KEY)
llm_followup   = ChatOpenAI(temperature=0.7, model="gpt-5.2", api_key=OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# Questions & criteria (unchanged)
# ---------------------------------------------------------------------------

questions = [
    {
        "question": {
            "en": "What happened and what did you do or try to do to resolve the issue?",
            "de": "Was ist passiert und was haben Sie getan oder versucht zu tun?",
            "es": "¿Qué sucedió y qué hizo o intentó hacer para resolver el problema?",
            "et": "Mis juhtus ja mida te tegite või proovisite teha, et lahendada probleemi?"
        },
        "criteria": [
            "a clear identification of the problem or situation that happened",
            "an understanding of the circumstances and environment in which the problem occurred",
            "description of the steps taken to address the problem once it was identified, along with the rationale for those actions",
        ]
    },
    {
        "question": {
            "en": "What were the reasons for these issues?",
            "de": "Was waren Gründe dafür dass es nicht funktioniert hat?",
            "es": "¿Cuáles fueron los motivos de estos problemas?",
            "et": "Mis olid nende probleemide põhjused?"
        },
        "criteria": [
            "review of the specific steps or actions taken that did not produce the desired result",
            "reflection on possible missteps, errors or misjudgments made during the process that might have contributed to the encountered difficulties",
            "reflection of external factors or conditions such as organizational, time, ethical, regulations, technological, environmental, or team-related challenges that might have contributed to the encountered difficulties",
        ]
    },
    {
        "question": {
            "en": "What have you learned from this for the future?",
            "de": "Was haben Sie daraus für die Zukunft gelernt?",
            "es": "¿Qué ha aprendido de esto para el futuro?",
            "et": "Mida olete sellest tulevikuks õppinud?"
        },
        "criteria": [
            "key lessons learned from the experience",
            "application of lessons learned to improve future situations or projects",
            "specific improvements to processes or approaches that have been or will be implemented as a result of the experience",
            "preventative measures to avoid similar failures in the future",
            "personal or professional growth as a result of this experience",
        ]
    }
]

# ---------------------------------------------------------------------------
# LLM functions – refactored to LCEL (pipe operator)
# ---------------------------------------------------------------------------

def classify_response(response_text: str, criteria: list, lang: str) -> dict:
    """Classify a student response against a list of criteria using structured output."""

    # Build a dynamic Pydantic model so the LLM returns exactly the criteria keys
    # We use with_structured_output for reliable JSON, but since criteria names are
    # dynamic, we fall back to a prompt-based JSON approach with LCEL.
    criteria_description = "\n".join(
        f'- "{c}": true if the response clearly includes elements of reflection related to this criterion, false otherwise'
        for c in criteria
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an evaluator. Classify the following student response (probably in {lang}, "
            "but it can be in another language) based on whether it clearly includes elements of "
            "reflection for each criterion.\n\n"
            "Criteria:\n{criteria_description}\n\n"
            "Return ONLY a valid JSON object where each key is the criterion text (exactly as given) "
            "and each value is the string \"True\" or \"False\"."
        )),
        ("human", "{response}")
    ])

    chain = prompt | llm_classifier | StrOutputParser()

    raw_output = chain.invoke({
        "response": response_text,
        "criteria_description": criteria_description,
        "lang": lang,
    })

    # Strip markdown code fences (e.g. ```json ... ```) if present
    cleaned = raw_output.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        output_dict = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM classification output: %s", cleaned)
        # Fallback: mark all criteria as unmet so the conversation can continue
        output_dict = {c: "False" for c in criteria}

    return output_dict


def generate_followup(response_text: str, unmet_criteria: list, lang: str) -> str:
    """Generate a follow-up question targeting unmet criteria."""
    criteria_str = ", ".join(unmet_criteria)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You help students reflect more deeply. Based on the student's response "
            "(probably in {lang} but possibly another language) and the unmet criteria, "
            "formulate a kind follow-up question.\n\n"
            "Rules:\n"
            "- The question MUST be written in {lang} using appropriate formal pronouns.\n"
            "- Be concise yet address ALL the unmet aspects.\n"
            "- Rephrase criteria contextually — don't copy them verbatim.\n"
            "- Use accessible language for non-expert students.\n"
            "- Do NOT thank the student or add unnecessary politeness."
        )),
        ("human", (
            "Student response: {response}\n\n"
            "Unmet criteria: {criteria}"
        ))
    ])

    chain = prompt | llm_followup | StrOutputParser()

    followup = chain.invoke({
        "response": response_text,
        "criteria": criteria_str,
        "lang": lang,
    })
    return followup.strip()

# ---------------------------------------------------------------------------
# Data helpers (unchanged logic)
# ---------------------------------------------------------------------------

def get_student_data(conversation_id):
    student = Student.query.filter_by(conversation_id=conversation_id).first()
    if student:
        return student.json_data
    return None

def save_student_data(student_data):
    with app.app_context():
        student = Student.query.filter_by(conversation_id=student_data['conversation_id']).first()
        if not student:
            cet = pytz.timezone('Europe/Berlin')
            student = Student(
                conversation_id=student_data['conversation_id'],
                name=student_data['name'],
                email=student_data['email'],
                language=student_data['language'],
                conversation_status='pending',
                json_data=student_data,
                start_time=datetime.now(cet)
            )
            db.session.add(student)
        else:
            student.json_data = student_data
            student.conversation_status = student_data.get('conversation_status', 'pending')

        if student.conversation_status == 'completed':
            cet = pytz.timezone('Europe/Berlin')
            student.end_time = datetime.now(cet)

        # Save responses
        for i, response_data in enumerate(student_data['responses']):
            response = Response.query.filter_by(student_id=student.id, question_number=i+1).first()
            if not response:
                response = Response(
                    student_id=student.id,
                    question_number=i+1,
                    question_text=response_data['question_text'],
                    final_unmet_criteria=response_data.get('unmet_criteria', [])
                )
                db.session.add(response)
            else:
                response.final_unmet_criteria = response_data.get('unmet_criteria', [])

            # Save attempts
            for j, attempt_data in enumerate(response_data['attempts']):
                attempt = Attempt.query.filter_by(response_id=response.id, attempt_number=j+1).first()
                if not attempt:
                    question_text = response_data['question_text'] if j == 0 else response_data['attempts'][j-1].get('next_followup_question', '')
                    attempt = Attempt(
                        response_id=response.id,
                        attempt_number=j+1,
                        response_type=attempt_data['response_type'],
                        question_text=question_text,
                        response_text=attempt_data['response'],
                        unmet_criteria=attempt_data.get('unmet_criteria', [])
                    )
                    db.session.add(attempt)
                else:
                    attempt.response_text = attempt_data['response']
                    attempt.unmet_criteria = attempt_data.get('unmet_criteria', [])

                # Save classifications
                for criterion, is_met in attempt_data['classification'].items():
                    classification = Classification.query.filter_by(attempt_id=attempt.id, criterion=criterion).first()
                    if not classification:
                        classification = Classification(
                            attempt_id=attempt.id,
                            criterion=criterion,
                            is_met=(is_met.lower() == 'true') if isinstance(is_met, str) else bool(is_met)
                        )
                        db.session.add(classification)
                    else:
                        classification.is_met = (is_met.lower() == 'true') if isinstance(is_met, str) else bool(is_met)

        db.session.commit()
        print(f"Saved data for student {student.id}")

# ---------------------------------------------------------------------------
# Helper: build end-of-conversation response
# ---------------------------------------------------------------------------

END_MESSAGES = {
    "en": "Thank you for your answers. You can download the conversation.",
    "de": "Vielen Dank für Ihre Antworten. Sie können das Gespräch herunterladen.",
    "es": "Gracias por sus respuestas. Puede descargar la conversación.",
    "et": "Täname teid vastuste eest. Saate vestluse alla laadida.",
}

def _end_conversation(student_data, lang):
    """Mark conversation completed and return end JSON."""
    student_data['conversation_status'] = 'completed'
    save_student_data(student_data)
    return jsonify({"end": True, "message": END_MESSAGES[lang]})

def _next_question_response(student_data, question_index, lang):
    """Return the next main question JSON."""
    return jsonify({
        "student_data": student_data,
        "question_index": question_index,
        "attempt": 0,
        "question": questions[question_index]["question"][lang],
    })

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    session.clear()
    session['language'] = None
    return render_template('index.html')

@app.route('/set_language', methods=['POST'])
def set_language():
    lang = request.json['language']
    session['language'] = lang
    return jsonify({"success": True})

@app.route('/start', methods=['POST'])
def start():
    data = request.json
    lang = session.get('language', 'en')
    student_data = {
        "conversation_id": str(uuid.uuid4()),
        "name": data['name'],
        "email": data['email'],
        "language": lang,
        "responses": [],
    }
    save_student_data(student_data)
    return jsonify({
        "student_data": student_data,
        "question_index": 0,
        "attempt": 0,
        "question": questions[0]["question"][lang],
    })

@app.route('/answer', methods=['POST'])
def answer():
    data = request.json
    question_index = data['question_index']
    attempt = data['attempt']
    response_text = data['response']
    student_data = get_student_data(data['student_data']['conversation_id'])
    if not student_data:
        return jsonify({"error": "Student data not found"}), 404

    lang = student_data['language']
    current_question = questions[question_index]
    question_id = f"question{question_index + 1}"

    # First attempt: create new question_data; otherwise retrieve existing
    if attempt == 0:
        unmet_criteria = current_question["criteria"]
        question_data = {
            "question_id": question_id,
            "question_text": current_question["question"][lang],
            "attempts": [],
            "unmet_criteria": unmet_criteria,
        }
        student_data["responses"].append(question_data)
    else:
        question_data = student_data["responses"][-1]
        unmet_criteria = question_data.get("unmet_criteria", current_question["criteria"])

    # Classify the response
    classification = classify_response(response_text, unmet_criteria, lang)

    response_type = "main" if attempt == 0 else "followup"
    attempt_data = {
        "attempt_number": attempt + 1,
        "response_type": response_type,
        "response": response_text,
        "classification": classification,
        "unmet_criteria": [
            criterion for criterion in unmet_criteria
            if str(classification.get(criterion, "False")).lower() != "true"
        ],
    }

    question_data["unmet_criteria"] = attempt_data["unmet_criteria"]
    all_criteria_met = len(question_data["unmet_criteria"]) == 0

    if not all_criteria_met:
        followup = generate_followup(response_text, question_data["unmet_criteria"], lang)
        attempt_data["next_followup_question"] = followup

    student_data["responses"][-1]["attempts"].append(attempt_data)
    save_student_data(student_data)

    # Decide next step
    move_to_next = all_criteria_met or attempt >= 2

    if move_to_next:
        if question_index < len(questions) - 1:
            return _next_question_response(student_data, question_index + 1, lang)
        else:
            return _end_conversation(student_data, lang)
    else:
        # Still have follow-up attempts left
        return jsonify({
            "student_data": student_data,
            "question_index": question_index,
            "attempt": attempt + 1,
            "question": attempt_data["next_followup_question"],
        })

@app.route('/download-chat', methods=['POST'])
def download_chat():
    conversation_id = request.json.get('conversation_id')
    student_data = get_student_data(conversation_id)
    if not student_data:
        return jsonify({"error": "Student data not found"}), 404

    lang = student_data.get('language', 'en')
    user_name = student_data.get('name', 'User')

    translations = {
        "en": {"chat_conversation": "Chat Conversation for", "question": "Question", "followup": "Follow-up question", "for_question": "for Question"},
        "de": {"chat_conversation": "Chat-Konversation für", "question": "Frage", "followup": "Folgefrage", "for_question": "zu Frage"},
        "es": {"chat_conversation": "Conversación de chat para", "question": "Pregunta", "followup": "Pregunta de seguimiento", "for_question": "para la Pregunta"},
        "et": {"chat_conversation": "Vestluse sisu kasutajale", "question": "Küsimus", "followup": "Järelküsimus", "for_question": "Küsimusele"},
    }
    t = translations[lang]

    chat_content = f"{t['chat_conversation']} {student_data['name']} ({student_data['email']})\n\n"

    for i, resp in enumerate(student_data['responses'], 1):
        chat_content += f"{t['question']} {i}: {resp['question_text']}\n\n"
        for j, att in enumerate(resp['attempts'], 1):
            if j == 1:
                chat_content += f"{user_name}: {att['response']}\n\n"
            else:
                followup_question = resp['attempts'][j-2].get('next_followup_question', 'N/A')
                chat_content += f"{t['followup']} {j-1} {t['for_question']} {i}: {followup_question}\n\n"
                chat_content += f"{user_name}: {att['response']}\n\n"
        chat_content += "\n"

    return chat_content, 200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': f'attachment; filename=chat_conversation_{conversation_id}.txt',
    }

@app.route('/end_session', methods=['POST'])
def end_session():
    data = request.json
    conversation_id = data.get('conversation_id')
    is_temporary = data.get('is_temporary', False)

    if conversation_id:
        with app.app_context():
            student = Student.query.filter_by(conversation_id=conversation_id).first()
            if student and student.conversation_status != 'completed':
                cet = pytz.timezone('Europe/Berlin')
                student.end_time = datetime.now(cet)
                if not is_temporary:
                    student.conversation_status = 'interrupted'
                db.session.commit()

    return jsonify({"success": True})

@app.route('/resume_session', methods=['POST'])
def resume_session():
    data = request.json
    conversation_id = data.get('conversation_id')

    if conversation_id:
        with app.app_context():
            student = Student.query.filter_by(conversation_id=conversation_id).first()
            if student and student.conversation_status != 'completed':
                student.end_time = None
                student.conversation_status = 'pending'
                db.session.commit()
                return jsonify({"success": True, "student_data": student.json_data})

    return jsonify({"success": False})

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def create_tables():
    with app.app_context():
        db.create_all()

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
