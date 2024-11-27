import telebot
import google.generativeai as genai
import time
import speech_recognition as sr
from pydub import AudioSegment
import os

bot = telebot.TeleBot("TELEGRAM API KEY")
genai.configure(api_key="GEMINI API KEY")  

generation_config = {
    "temperature": 1,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", 
        "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", 
        "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", 
        "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", 
        "threshold": "BLOCK_NONE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-8b", #gemini-1.5-pro, gemini-1.5-flash, gemini-1.5-flash-8b, gemini-1.0-pro, learnlm-1.5-pro-experimental
    generation_config=generation_config,
    safety_settings=safety_settings)

conv = model.start_chat()

user_contexts = {}

personalities = {  # añade las personalidades aqui
    "asistente": "eres un asistente profesional y educado.",
    "amigable": "Responde de manera alegre, como si estuvieras hablando con un amigo.",
} 

current_personality = "asistente"  # personalidad predeterminada
MAX_TOKENS_CONTEXT = 34000  # limite de tokens para el contexto


def estimate_tokens(text):
    return len(text) // 4 # cuantos caracteres equivale un token, en este caso 4


def truncate_context(context, max_tokens):
    total_tokens = 0
    truncated_context = []

    for message in reversed(context): 
        tokens = estimate_tokens(message)
        if total_tokens + tokens > max_tokens:
            break
        truncated_context.insert(0, message) 
        total_tokens += tokens

    return truncated_context


@bot.message_handler(commands=['set_personality'])
def set_personality(message):
    global current_personality
    personality = message.text.split(' ', 1)[-1].strip().lower()
    if personality in personalities:
        current_personality = personality
        bot.reply_to(message, f"Personalidad cambiada a: {personality}")
    else:
        bot.reply_to(message, "Personalidad no reconocida")


@bot.message_handler(commands=['clear_context'])
def clear_context(message):
    user_id = message.chat.id
    
    if user_id in user_contexts:
        del user_contexts[user_id]
        bot.reply_to(message, "El contexto ha sido borrado")

@bot.message_handler(commands=['new_chat'])
def new_chat(message):

    global conv
    user_id = message.chat.id

    # reiniciar el contexto
    user_contexts[user_id] = []

    # reiniciar la conversación con la api de gemini
    conv = model.start_chat()

    bot.reply_to(message, "Se ha iniciado una nueva conversacion")


@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("voice_message.ogg", "wb") as audio_file:
        audio_file.write(downloaded_file)

    audio = AudioSegment.from_ogg("voice_message.ogg")
    audio.export("voice_message.wav", format="wav")

    recognizer = sr.Recognizer()
    with sr.AudioFile("voice_message.wav") as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data, language="es-ES")

            global current_personality
            user_id = message.chat.id
            prompt_with_personality = f"{personalities[current_personality]} {text}"

            if user_id not in user_contexts:
                user_contexts[user_id] = []
            user_contexts[user_id].append(prompt_with_personality)

            user_contexts[user_id] = truncate_context(user_contexts[user_id], MAX_TOKENS_CONTEXT)

            bot.send_chat_action(user_id, action='typing')
            time.sleep(1)

            full_context = " ".join(user_contexts[user_id])
            conv.send_message(full_context)
            response = conv.last.text if conv.last else "hubo un problema al generar la respuesta"

            user_contexts[user_id].append(response)
            bot.reply_to(message, response)

        except sr.UnknownValueError:
            bot.reply_to(message, "Lo siento, no pude entenderte")
        except sr.RequestError:
            bot.reply_to(message, "Mejor escribe porque no te puedo escuchar")

    os.remove("voice_message.ogg")
    os.remove("voice_message.wav")


@bot.message_handler(func=lambda m: True)
def echo_all(message):
    global current_personality
    user_id = message.chat.id
    prompt_with_personality = f"{personalities[current_personality]} {message.text}"

    if user_id not in user_contexts:
        user_contexts[user_id] = []
    user_contexts[user_id].append(prompt_with_personality)

    user_contexts[user_id] = truncate_context(user_contexts[user_id], MAX_TOKENS_CONTEXT)

    bot.send_chat_action(user_id, action='typing')
    time.sleep(1)

    full_context = " ".join(user_contexts[user_id])
    try:
        conv.send_message(full_context)
        response = conv.last.text if conv.last else "hubo un problema al generar la respuesta"
    except Exception as e:
        response = f"Hubo un error al procesar tu mensaje: {str(e)}"

    user_contexts[user_id].append(response)
    bot.reply_to(message, response)


bot.infinity_polling()
