from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import JSON
from datetime import datetime
import pytz
import uuid
import os

from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the Student model
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

# Initialize OpenAI LLM
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm1 = ChatOpenAI(temperature=0.0, model="gpt-4o", api_key=OPENAI_API_KEY)
llm2 = ChatOpenAI(temperature=0.7, model="gpt-4o", api_key=OPENAI_API_KEY)

# Define questions and criteria
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

# Function to classify the response
def classify_response(response, criteria, lang):
    criteria_schemas = [
        ResponseSchema(
            name=criterion,
            description=f"Answer True if the response clearly includes elements of reflection related to '{criterion}', False if it is not met."
        )
        for criterion in criteria
    ]

    output_parser = StructuredOutputParser.from_response_schemas(criteria_schemas)
    format_instructions = output_parser.get_format_instructions()

    prompt_template = """\
    Classify the following response probably given in {lang}, but that can also be in another language, based on if the response clearly includes elements of reflection related to:

    {criteria}

    Response: {response}

    {format_instructions}
    """

    prompt = PromptTemplate(
        input_variables=["response", "criteria", "format_instructions", "lang"],
        template=prompt_template
    )

    chain = LLMChain(llm=llm1, prompt=prompt)

    input_variables = {
        "response": response,
        "criteria": ", ".join(criteria),
        "format_instructions": format_instructions,
        "lang": lang
    }

    classification = chain.run(input_variables)

    output_dict = output_parser.parse(classification)
    return output_dict

# Function to generate a follow-up question
def generate_followup(response, unmet_criteria, lang):
    criteria_str = ", ".join(unmet_criteria)
    prompt = PromptTemplate(
        input_variables=["response", "criteria", "lang"],
        template="Based on the given response, probably given in {lang} but that can also be in another language, and the aspects that still need clarification according to these criteria: {criteria}\n\nResponse: {response}\n\nPlease start by understanding the criteria and the student's answer. Then, formulate a kind follow-up question and make sure that it is explicitly written in {lang}. Use the appropriate formal pronouns and verb forms in {lang}. The question should be concise and short when possible, yet focused on addressing all the specific unmet aspects that require further explanation, as well as directly related to the content of the student's response whenever possible. When crafting the question, try to rephrase the criteria contextually instead of using their text as it is, as well as try using language that is accessible to non-expert students. No need to thank for the answer or to include other unnecessary politeness or information.",

    )
    chain = LLMChain(llm=llm2, prompt=prompt)
    followup = chain.run(response=response, criteria=criteria_str, lang=lang)
    return followup.strip()

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
                    # For the main question, use the question from the response_data
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
                            is_met=(is_met.lower() == 'true')
                        )
                        db.session.add(classification)
                    else:
                        classification.is_met = (is_met.lower() == 'true')
        
        db.session.commit()
        print(f"Saved data for student {student.id}")

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
        "responses": []
    }
    save_student_data(student_data)
    return jsonify({
        "student_data": student_data,
        "question_index": 0,
        "attempt": 0,
        "question": questions[0]["question"][lang]
    })

@app.route('/answer', methods=['POST'])
def answer():
    data = request.json
    question_index = data['question_index']
    attempt = data['attempt']
    response = data['response']
    student_data = get_student_data(data['student_data']['conversation_id'])
    if not student_data:
        return jsonify({"error": "Student data not found"}), 404
    
    lang = student_data['language']
    current_question = questions[question_index]
    question_id = f"question{question_index + 1}"

    if attempt == 0:
        unmet_criteria = current_question["criteria"]
        question_data = {
            "question_id": question_id,
            "question_text": current_question["question"][lang],
            "attempts": [],
            "unmet_criteria": unmet_criteria
        }
        student_data["responses"].append(question_data)
    else:
        question_data = student_data["responses"][-1]
        unmet_criteria = question_data.get("unmet_criteria", current_question["criteria"])

    classification = classify_response(response, unmet_criteria, lang)

    response_type = "main" if attempt == 0 else "followup"
    attempt_data = {
        "attempt_number": attempt + 1,
        "response_type": response_type,
        "response": response,
        "classification": classification,
        "unmet_criteria": [criterion for criterion in unmet_criteria if classification[criterion] == "False"]
    }

    question_data["unmet_criteria"] = attempt_data["unmet_criteria"]

    all_criteria_met = len(question_data["unmet_criteria"]) == 0

    if not all_criteria_met:
        followup = generate_followup(response, question_data["unmet_criteria"], lang)
        attempt_data["next_followup_question"] = followup

    student_data["responses"][-1]["attempts"].append(attempt_data)
    
    save_student_data(student_data)
    
    if all_criteria_met:
        if question_index < len(questions) - 1:
            question_index += 1
            return jsonify({
                "student_data": student_data,
                "question_index": question_index,
                "attempt": 0,
                "question": questions[question_index]["question"][lang]
            })
        else:
            # This is where the conversation ends
            student_data['conversation_status'] = 'completed'
            save_student_data(student_data)
            return jsonify({"end": True, "message": {
                "en": "Thank you for your answers. You can download the conversation.",
                "de": "Vielen Dank für Ihre Antworten. Sie können das Gespräch herunterladen.",
                "es": "Gracias por sus respuestas. Puede descargar la conversación.",
                "et": "Täname teid vastuste eest. Saate vestluse alla laadida."
            }[lang]})
    else:
        if attempt < 2:
            return jsonify({
                "student_data": student_data,
                "question_index": question_index,
                "attempt": attempt + 1,
                "question": attempt_data["next_followup_question"],
            })
        else:
            if question_index < len(questions) - 1:
                question_index += 1
                return jsonify({
                    "student_data": student_data,
                    "question_index": question_index,
                    "attempt": 0,
                    "question": questions[question_index]["question"][lang]
                })
            else:
                # This is where the conversation ends
                student_data['conversation_status'] = 'completed'
                save_student_data(student_data)
                return jsonify({"end": True, "message": {
                    "en": "Thank you for your answers. You can download the conversation.",
                    "de": "Vielen Dank für Ihre Antworten. Sie können das Gespräch herunterladen.",
                    "es": "Gracias por sus respuestas. Puede descargar la conversación.",
                    "et": "Täname teid vastuste eest. Saate vestluse alla laadida."
                }[lang]})

@app.route('/download-chat', methods=['POST'])
def download_chat():
    conversation_id = request.json.get('conversation_id')
    student_data = get_student_data(conversation_id)
    if not student_data:
        return jsonify({"error": "Student data not found"}), 404

    lang = student_data.get('language', 'en')
    user_name = student_data.get('name', 'User')  # Get the user's name, default to 'User' if not found

    # Translations for the chat download
    translations = {
        "en": {
            "chat_conversation": "Chat Conversation for",
            "question": "Question",
            "followup": "Follow-up question",
            "for_question": "for Question"
        },
        "de": {
            "chat_conversation": "Chat-Konversation für",
            "question": "Frage",
            "followup": "Folgefrage",
            "for_question": "zu Frage"
        },
        "es": {
            "chat_conversation": "Conversación de chat para",
            "question": "Pregunta",
            "followup": "Pregunta de seguimiento",
            "for_question": "para la Pregunta"
        },
        "et": {
            "chat_conversation": "Vestluse sisu kasutajale",
            "question": "Küsimus",
            "followup": "Järelküsimus",
            "for_question": "Küsimusele"
        }
    }

    t = translations[lang]

    chat_content = f"{t['chat_conversation']} {student_data['name']} ({student_data['email']})\n\n"

    for i, response in enumerate(student_data['responses'], 1):
        chat_content += f"{t['question']} {i}: {response['question_text']}\n\n"
        for j, attempt in enumerate(response['attempts'], 1):
            if j == 1:
                chat_content += f"{user_name}: {attempt['response']}\n\n"
            else:
                # Use the 'next_followup_question' from the previous attempt for follow-up questions
                followup_question = response['attempts'][j-2].get('next_followup_question', 'N/A')
                chat_content += f"{t['followup']} {j-1} {t['for_question']} {i}: {followup_question}\n\n"
                chat_content += f"{user_name}: {attempt['response']}\n\n"
        chat_content += "\n"

    return chat_content, 200, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Content-Disposition': f'attachment; filename=chat_conversation_{conversation_id}.txt'
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

def create_tables():
    with app.app_context():
        db.create_all()
        #print("Database tables created")

# Call this function before running the app
if __name__ == '__main__':
    create_tables()
    app.run(debug=True)