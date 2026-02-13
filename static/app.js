// static/app.js

let studentData = null;
let questionIndex = 0;
let attempt = 0;
let firstQuestion = '';
let chatHistory = []; // Array to store all chat messages
let selectedLanguage = '';
let isConversationEnded = false;
let isRefreshing = false;

// Define variables for timeout management
let retryTimeout;
let retryAttempt = 0;
const RETRY_LIMIT = 1;
const RETRY_INTERVAL = 30000; // 30 seconds

document.addEventListener('DOMContentLoaded', function() {
    const languageButtons = document.querySelectorAll('.language-btn');
    languageButtons.forEach(button => {
        button.addEventListener('click', function() {
            selectedLanguage = this.getAttribute('data-lang');
            setLanguage(selectedLanguage);
        });
    });

    window.addEventListener('beforeunload', handleBeforeUnload);
});

function handleBeforeUnload(event) {
    if (!isConversationEnded) {
        endSession(true);
        // Add a confirmation dialog
        // event.preventDefault();
        // event.returnValue = '';
    }
}

function setLanguage(lang) {
    fetch('/set_language', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ language: lang }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('language-selection').style.display = 'none';
            document.getElementById('consent-form').style.display = 'block';
            updateUILanguage(lang);
        }
    });
}

function updateUILanguage(lang) {
    const translations = {
        "en": {
            "consentTitle": "Consent Form",
            "consentContent": `<p>This website uses the OpenAI API to analyze your responses. We would like to inform you about the following points:</p>
            <ol>
                <li>Your data is always processed anonymously.</li>
                <li>No information is stored that could identify you or the institution you work for.</li>
                <li>The data is used exclusively for research purposes.</li>
                <li>The contents of your messages are processed by OpenAI models based on OpenAI's <a href="https://openai.com/policies/row-terms-of-use" target="_blank">Terms of Use</a>.</li>
            </ol>
            <p>By clicking "Agree", you confirm that you have read and understood this information.</p>`,
            "agreeButton": "Agree",
            "startTitle": "ReflectionApp",
            "namePlaceholder": "Name",
            "emailPlaceholder": "Email",
            "startButton": "Start",
            "responsePlaceholder": "Your answer...",
            "sendButton": "Send",
            "downloadButton": "Download conversation",
            "aiTyping": "AI is typing..."
        },
        "de": {
            "consentTitle": "Einwilligungserklärung",
            "consentContent": `<p>Diese Website verwendet die OpenAI API, um Ihre Antworten zu analysieren. Wir möchten Sie über folgende Punkte informieren:</p>
            <ol>
                <li>Ihre Daten werden immer anonym verarbeitet.</li>
                <li>Es werden keine Informationen gespeichert, die Sie oder die Institution, für die Sie arbeiten, identifizieren könnten.</li>
                <li>Die Daten werden ausschließlich zu Forschungszwecken verwendet.</li>
                <li>Die Inhalte Ihrer Nachrichten werden von OpenAI-Modellen auf der Grundlage der <a href="https://openai.com/policies/row-terms-of-use" target="_blank">Geschäftsbedingungen</a> von OpenAI verarbeitet.</li>
            </ol>
            <p>Durch Klicken auf "Einverstanden" bestätigen Sie, dass Sie diese Informationen gelesen und verstanden haben.</p>`,
            "agreeButton": "Einverstanden",
            "startTitle": "ReflectionApp",
            "namePlaceholder": "Name",
            "emailPlaceholder": "E-Mail",
            "startButton": "Start",
            "responsePlaceholder": "Ihre Antwort...",
            "sendButton": "Senden",
            "downloadButton": "Gespräch herunterladen",
            "aiTyping": "KI schreibt..."
        },
        "es": {
            "consentTitle": "Formulario de Consentimiento",
            "consentContent": `<p>Este sitio web utiliza la API de OpenAI para analizar sus respuestas. Nos gustaría informarle sobre los siguientes puntos:</p>
            <ol>
                <li>Sus datos siempre se procesan de forma anónima.</li>
                <li>No se almacena ninguna información que pueda identificarle a usted o a la institución para la que trabaja.</li>
                <li>Los datos se utilizan exclusivamente con fines de investigación.</li>
                <li>El contenido de sus mensajes es procesado por modelos de OpenAI basados en los <a href="https://openai.com/policies/row-terms-of-use" target="_blank">Términos de Uso</a> de OpenAI.</li>
            </ol>
            <p>Al hacer clic en "Aceptar", confirma que ha leído y entendido esta información.</p>`,
            "agreeButton": "Aceptar",
            "startTitle": "ReflectionApp",
            "namePlaceholder": "Nombre",
            "emailPlaceholder": "Correo electrónico",
            "startButton": "Comenzar",
            "responsePlaceholder": "Su respuesta...",
            "sendButton": "Enviar",
            "downloadButton": "Descargar conversación",
            "aiTyping": "La IA está escribiendo..."
        },
        "et": {
            "consentTitle": "Nõusoleku vorm",
            "consentContent": `<p>See veebisait kasutab teie vastuste analüüsimiseks OpenAI API-t. Soovime teid teavitada järgmistest punktidest:</p>
            <ol>
                <li>Teie andmeid töödeldakse alati anonüümselt.</li>
                <li>Ei salvestata mingit teavet, mis võiks tuvastada teid või asutust, kus te töötate.</li>
                <li>Andmeid kasutatakse ainult teadusuuringute eesmärgil.</li>
                <li>Teie sõnumite sisu töödeldakse OpenAI mudelite poolt vastavalt OpenAI <a href="https://openai.com/policies/row-terms-of-use" target="_blank">kasutustingimustele</a>.</li>
            </ol>
            <p>Klõpsates "Nõustun", kinnitate, et olete selle teabe läbi lugenud ja sellest aru saanud.</p>`,
            "agreeButton": "Nõustun",
            "startTitle": "ReflectionApp",
            "namePlaceholder": "Nimi",
            "emailPlaceholder": "E-post",
            "startButton": "Alusta",
            "responsePlaceholder": "Teie vastus...",
            "sendButton": "Saada",
            "downloadButton": "Laadi vestlus alla",
            "aiTyping": "Tehisintellekt kirjutab..."
        }
    };

    const t = translations[lang];

    document.getElementById('consent-title').textContent = t.consentTitle;
    document.querySelector('.consent-content').innerHTML = t.consentContent;
    document.getElementById('consent-btn').textContent = t.agreeButton;
    document.querySelector('#start-form h1').textContent = t.startTitle;
    document.getElementById('name').placeholder = t.namePlaceholder;
    document.getElementById('email').placeholder = t.emailPlaceholder;
    document.getElementById('start-btn').textContent = t.startButton;
    document.getElementById('response-input').placeholder = t.responsePlaceholder;
    document.getElementById('send-btn').textContent = t.sendButton;
    document.getElementById('download-btn').textContent = t.downloadButton;
}

document.getElementById('consent-btn').addEventListener('click', showStartForm);
document.getElementById('start-btn').addEventListener('click', startChat);
document.getElementById('send-btn').addEventListener('click', sendResponse);

const downloadButton = '<button id="download-btn" class="btn" style="display:none;">Download Conversation</button>';
document.getElementById('chat-container').insertAdjacentHTML('beforeend', downloadButton);
document.getElementById('download-btn').addEventListener('click', downloadChat);

const introMessages = {
    "en": [
        "This is an interactive form designed to help you thoroughly reflect on the challenges you encountered during your project.",
        //"In the Google form, you described the obstacles you faced during the post-phase of successfully implementing your Learning Analytics application in your organization.",
        "Select one obstacle that you encountered during your project and answer the three questions that will be displayed below. If more details are needed, additional questions will follow each of the three main questions.",
        "The entire process takes between 10 and 15 minutes. Please do not close the window until you have answered all the questions, as your answers may be lost.",
        "Let's start with the questions. Remember that the questions relate to one of the obstacles you chose."
    ],
    "de": [
        "Dies ist ein interaktives Formular, das Ihnen dabei helfen soll, die Herausforderungen, denen Sie während Ihres Projekts begegnet sind, gründlich zu reflektieren.",
        "Im Google-Formular haben Sie die Hindernisse beschrieben, auf die Sie während der Nachphase bei der erfolgreichen Implementierung Ihrer Learning Analytics-Anwendung in Ihrer Organisation gestoßen sind.",
        "Wählen Sie hier eines dieser Hindernisse aus und beantworten Sie die drei Fragen, die unten angezeigt werden. Falls mehr Details benötigt werden, folgen zusätzliche Fragen zu jeder der drei Hauptfragen.",
        "Der gesamte Vorgang dauert zwischen 10 und 15 Minuten. Bitte schließen Sie das Fenster nicht, bevor Sie alle Fragen beantwortet haben, da Ihre Antworten sonst verloren gehen könnten.",
        "Lassen Sie uns mit den Fragen beginnen. Vergessen Sie nicht, dass sich die Fragen auf eines der von Ihnen gewählten Hindernisse beziehen."
    ],
    "es": [
        "Este es un formulario interactivo diseñado para ayudarle a reflexionar a fondo sobre los desafíos que encontró durante su proyecto.",
        //"En el formulario de Google, describió los obstáculos que enfrentó durante la fase posterior a la implementación exitosa de su aplicación de Análisis de Aprendizaje en su organización.",
        "Seleccione un obstáculo que haya encontrado durante su proyecto y responda a las tres preguntas que aparecerán a continuación.  Si se necesitan más detalles, a cada una de las tres preguntas principales le seguirán otras.",
        "Todo el proceso lleva entre 10 y 15 minutos. Por favor, no cierre la ventana hasta que haya respondido todas las preguntas, ya que sus respuestas podrían perderse.",
        "Comencemos con las preguntas. Recuerde que las preguntas se refieren a uno de los obstáculos que eligió."
    ],
    "et": [
        "See on interaktiivne vorm, mis on loodud selleks, et aidata teil põhjalikult mõelda väljakutsetele, millega oma projekti käigus kokku puutusite.",
        //"Google'i vormis kirjeldasite takistusi, millega puutusite kokku oma õppeanalüütika rakenduse edukal rakendamisel oma organisatsioonis.",
        "Valige takistus, millega olete oma projekti käigus kokku puutunud, ja vastake kolmele alljärgnevale küsimusele.  Kui on vaja rohkem üksikasju, järgnevad igale kolmele põhiküsimusele teised küsimused",
        "Kogu protsess võtab aega 10 kuni 15 minutit. Palun ärge sulgege akent enne, kui olete vastanud kõigile küsimustele, kuna teie vastused võivad kaduma minna.",
        "Alustame küsimustega. Pidage meeles, et küsimused on seotud ühega teie valitud takistustest."
    ]
};

function showStartForm() {
    document.getElementById('consent-form').style.display = 'none';
    document.getElementById('start-form').style.display = 'block';
}

function startChat() {
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;

    if (!name || !email) {
        alert(selectedLanguage === 'de' ? 'Bitte geben Sie sowohl Namen als auch E-Mail-Adresse ein.' :
              selectedLanguage === 'es' ? 'Por favor, ingrese tanto el nombre como el correo electrónico.' :
              selectedLanguage === 'et' ? 'Palun sisestage nii nimi kui ka e-posti aadress.' :
              'Please enter both name and email.');
        return;
    }

    // Try to resume an existing session
    fetch('/resume_session', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            studentData = data.student_data;
            questionIndex = studentData.responses.length;
            attempt = 0;
            document.getElementById('start-form').style.display = 'none';
            document.getElementById('chat-container').style.display = 'block';
            displayPreviousConversation(studentData);
            showNextQuestion();
        } else {
            // Start a new session
            fetch('/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name, email }),
            })
            .then(response => response.json())
            .then(data => {
                studentData = data.student_data;
                questionIndex = data.question_index;
                attempt = data.attempt;
                firstQuestion = data.question;
                document.getElementById('start-form').style.display = 'none';
                document.getElementById('chat-container').style.display = 'block';
                showIntroMessages(0);
            });
        }
    });
}

function showIntroMessages(index) {
    if (index < introMessages[selectedLanguage].length) {
        showTypingIndicator();
        setTimeout(() => {
            removeTypingIndicator();
            addMessage(introMessages[selectedLanguage][index], 'intro');
            showIntroMessages(index + 1);
        }, 5000);
    } else {
        showTypingIndicator();
        setTimeout(() => {
            removeTypingIndicator();
            addMessage(firstQuestion, 'question', true);
        }, 1500);
    }
}

function sendResponse(event) {
    event.preventDefault();  // Prevent form from submitting normally

    const response = document.getElementById('response-input').value;

    if (!response) {
        alert(selectedLanguage === 'de' ? 'Bitte geben Sie eine Antwort ein.' :
              selectedLanguage === 'es' ? 'Por favor, ingrese una respuesta.' :
              selectedLanguage === 'et' ? 'Palun sisestage vastus.' :
              'Please enter a response.');
        return;
    }

    addMessage(response, 'response');
    showTypingIndicator();

    // Send the request to OpenAI
    fetchResponseFromOpenAI(response);
    
    // Clear the input field
    document.getElementById('response-input').value = '';
}

// Function to handle fetching response from OpenAI
function fetchResponseFromOpenAI(response) {
    // Clear any previous retry attempt
    clearTimeout(retryTimeout);

    fetch('/answer', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            student_data: studentData,
            question_index: questionIndex,
            attempt: attempt,
            response: response,
        }),
    })
    .then(response => response.json())
    .then(data => {
        clearTimeout(retryTimeout); // Clear timeout if a response is received
        setTimeout(() => {
            removeTypingIndicator();
            if (data.end) {
                isConversationEnded = true;
                addMessage(data.message, 'question', false, true);
                document.getElementById('response-form').style.display = 'none';
                document.getElementById('download-btn').style.display = 'block';
            } else {
                // Reset retry attempts since we received a valid response
                retryAttempt = 0;

                // Process the next question
                studentData = data.student_data;
                questionIndex = data.question_index;
                attempt = data.attempt;
                addMessage(data.question, 'question', attempt === 0);
            }
        }, 1500);
    })
    .catch(error => {
        console.error('Error with OpenAI request:', error);
        // Trigger retry after the set interval
        retryAfterTimeout(response);
    });

    // Set a timeout to retry if no response within 30 seconds
    retryTimeout = setTimeout(() => {
        retryAfterTimeout(response);
    }, RETRY_INTERVAL);
}

function retryAfterTimeout(response) {
    if (retryAttempt < RETRY_LIMIT) {
        retryAttempt++;
        console.log(`Retry attempt ${retryAttempt}`);
        // Resend the request to OpenAI
        fetchResponseFromOpenAI(response);
    } else {
        // After the second failed attempt, show the error message in the selected language
        clearTimeout(retryTimeout);
        removeTypingIndicator();
        const errorMessages = {
            "en": "There was an error with the OpenAI service. Please rephrase your response and try again. If it still doesn't work, please restart the website!",
            "de": "Es gab einen Fehler mit dem OpenAI-Dienst. Bitte formulieren Sie Ihre Antwort um und versuchen Sie es erneut. Wenn es immer noch nicht funktioniert, starten Sie bitte die Website neu!",
            "es": "Hubo un error con el servicio de OpenAI. Por favor, reformule su respuesta e intente nuevamente. Si aún no funciona, ¡reinicie el sitio web!",
            "et": "OpenAI teenusega tekkis viga. Palun sõnastage oma vastus ümber ja proovige uuesti. Kui see ikka ei tööta, taaskäivitage palun veebisait!"
        };
        addMessage(errorMessages[selectedLanguage], 'error');
    }
}

// Function to add message in the chatbox
function addMessage(message, type, isMainQuestion = false, isFinalMessage = false) {
    const chatBox = document.getElementById('chat-box');
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', type);

    if (type === 'question' && isMainQuestion) {
        messageElement.classList.add('main-question');
        messageElement.setAttribute('data-question-number', `${selectedLanguage === 'de' ? 'Frage' : 
                                                              selectedLanguage === 'es' ? 'Pregunta' : 
                                                              selectedLanguage === 'et' ? 'Küsimus' : 
                                                              'Question'} ${questionIndex + 1}`);
    } else if (type === 'question' && !isMainQuestion && !isFinalMessage) {
        messageElement.classList.add('followup-question');
        // Determine if this is the first or second follow-up question
        const isFirstFollowUp = chatHistory.filter(entry => 
            entry.type === 'question' && 
            !entry.isMainQuestion && 
            entry.questionIndex === questionIndex
        ).length === 0;

        if (isFirstFollowUp) {
            messageElement.setAttribute('data-followup-label', 
                selectedLanguage === 'de' ? `Einige weitere Details zu Frage ${questionIndex + 1}` :
                selectedLanguage === 'es' ? `Más información sobre la Pregunta ${questionIndex + 1}` :
                selectedLanguage === 'et' ? `Lisateavet ${questionIndex + 1}. küsimuse kohta` :
                `Some more details for Question ${questionIndex + 1}`
            );
        } else {
            messageElement.setAttribute('data-followup-label', 
                selectedLanguage === 'de' ? `Noch ein paar Details zu Frage ${questionIndex + 1}` :
                selectedLanguage === 'es' ? `Algunos detalles más sobre la Pregunta ${questionIndex + 1}` :
                selectedLanguage === 'et' ? `Mõned täiendavad üksikasjad Küsimusele ${questionIndex + 1}` :
                `A few more details on Question ${questionIndex + 1}`
            );
        }
    } else if (type === 'intro') {
        messageElement.classList.add('intro-message');
        messageElement.setAttribute('data-intro-label', 
            selectedLanguage === 'de' ? 'Richtlinien' :
            selectedLanguage === 'es' ? 'Directrices' :
            selectedLanguage === 'et' ? 'Juhised' :
            'Guidelines'
        );
    } else if (type === 'error') {
        messageElement.classList.add('error-message');
    }

    messageElement.textContent = message;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Save the message to chatHistory
    chatHistory.push({
        message: message,
        type: type,
        isMainQuestion: isMainQuestion,
        isFinalMessage: isFinalMessage,
        questionIndex: questionIndex
    });
}

function showTypingIndicator() {
    const chatBox = document.getElementById('chat-box');
    const typingIndicator = document.createElement('div');
    typingIndicator.id = 'typing-indicator';
    typingIndicator.classList.add('message', 'question');
    typingIndicator.textContent = selectedLanguage === 'de' ? 'KI schreibt...' :
                                  selectedLanguage === 'es' ? 'La IA está escribiendo...' :
                                  selectedLanguage === 'et' ? 'Tehisintellekt kirjutab...' :
                                  'AI is typing...';
    chatBox.appendChild(typingIndicator);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Disable the send button
    document.getElementById('send-btn').disabled = true;
}

function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }

    // Enable the send button
    document.getElementById('send-btn').disabled = false;
}

function downloadChat() {
    setTimeout(() => {
        fetch('/download-chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(studentData),
        })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'chat_conversation.txt';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        });
    }, 1000);  // Add a 1-second delay before generating the download
}

function endSession(isTemporary = false) {
    if (studentData) {
        fetch('/end_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: studentData.conversation_id,
                is_temporary: isTemporary
            }),
        });
    }
}

function periodicSave() {
    if (studentData && !isConversationEnded) {
        endSession(true);
    }
}

// Call periodicSave every 30 seconds
setInterval(periodicSave, 30000);