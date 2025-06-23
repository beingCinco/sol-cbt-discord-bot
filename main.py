import os
import discord
from discord import app_commands
import requests
import time
import logging
from datetime import datetime, timedelta
import random
import langdetect
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug.log')
    ]
)
logger = logging.getLogger('discord')

# ===== LANGUAGE CONFIGURATION =====
LANGUAGE_INSTRUCTION = "\n\nRespond in the same language as the user's message."
ERROR_TRANSLATIONS = {
    'es': {
        'processing': "🤔 Necesito un momento para procesar eso. ¿Podrías reformular o añadir más contexto?",
        'error': "⚠️ Mis pensamientos están enredados ahora. ¿Podríamos intentarlo de nuevo?",
        'crisis': (
            "🚨 Estoy preocupado por lo que compartes. Por favor contacta inmediatamente:\n"
            "• Línea de Texto de Crisis: Envía 'HOME' al 741741\n"
            "• Ayuda Internacional: https://www.iasp.info/resources/Crisis_Centres/\n"
            "• Servicios de emergencia locales"
        )
    },
    'fr': {
        'processing': "🤔 J'ai besoin d'un moment pour traiter cela. Pourriez-vous reformuler ou ajouter plus de contexte?",
        'error': "⚠️ Mes pensées sont embrouillées en ce moment. Pourrions-nous réessayer?",
        'crisis': (
            "🚨 Je suis préoccupé par ce que vous partagez. Veuillez contacter immédiatement :\n"
            "• Ligne de texte de crise : Envoyez HOME au 741741\n"
            "• Aide internationale : https://www.iasp.info/resources/Crisis_Centres/\n"
            "• Vos services d'urgence locaux"
        )
    },
    'de': {
        'processing': "🤔 Ich brauche einen Moment, um das zu verarbeiten. Könntest du das umformulieren oder mehr Kontext hinzufügen?",
        'error': "⚠️ Meine Gedanken sind gerade verwirrt. Könnten wir es noch einmal versuchen?",
        'crisis': (
            "🚨 Ich mache mir Sorgen über das, was du teilst. Bitte wende dich sofort an:\n"
            "• Crisis Text Line: Sende HOME an 741741\n"
            "• Internationale Hilfe: https://www.iasp.info/resources/Crisis_Centres/\n"
            "• Deine örtlichen Notdienste"
        )
    },
    # Add more languages as needed
}

# ===== HARDCODED CONFIGURATION =====
CONFIG = {
    "DISCORD_TOKEN": "DISCORD_TOKEN",
    "SERVER_ID": "SERVER_ID",
    "HF_API_KEY": "HF_API_KEY",   
    "MODEL": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "CRISIS_KEYWORDS": ["suicide", "self-harm", "kill myself", "end it all"],
    "MEMORY_DURATION": 24,
    "MAX_HISTORY": 6,
    "SUPPORTED_LANGUAGES": ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja']
}

# ===== ENHANCED THERAPEUTIC PROMPTS =====
INITIAL_SYSTEM_PROMPT = """You are Sol, a compassionate therapist specializing in relationship dynamics. 
Respond naturally using these therapeutic elements:
1. VALIDATION: Acknowledge their feelings ("That sounds really tough...")
2. EXPLORATION: Ask an open-ended question to deepen understanding
3. REFRAME: Offer an attachment-based perspective without jargon
4. ACTION: Suggest one small, manageable step
Weave these into a flowing 2-3 sentence response. Never number points. Use natural interjections like "Hmm" or "I see"."""

FOLLOW_UP_SYSTEM_PROMPT = """Continue as Sol in an ongoing therapy conversation. Prioritize:
- Building on previous exchanges naturally
- Using conversational markers ("Ah, I understand...", "That makes me wonder...")
- Balancing empathy with gentle challenges
- Suggesting micro-actions based on the dialogue
Respond in 1-2 sentences maximum, keeping it conversational."""

# ===== THERAPIST PERSONA ELEMENTS =====
EMPATHY_MARKERS = [
    "Hmm, that sounds really challenging...",
    "Oh, I can sense the weight of that...",
    "Ah, I understand why you'd feel that way...",
    "That makes complete sense given what you're describing...",
    "I hear the frustration in that..."
]

REFLECTIVE_PHRASES = [
    "What comes up for you when you consider...",
    "I'm curious what that pattern might be showing...",
    "Where do you feel that in your body right now?",
    "What would it look like if we approached this differently?",
    "How does that resonate with your experience?"
]

ACTION_FRAMING = [
    "How about we try...",
    "What if you experimented with...",
    "I wonder what would happen if...",
    "Maybe you could test out...",
    "Consider trying this small step..."
]

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sol-therapy-bot')

# ===== DISCORD BOT SETUP =====
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ===== LANGUAGE DETECTION =====
def detect_language(text: str) -> str:
    """Robust language detection with validation"""
    if not text.strip():
        return 'en'

    try:
        # Try detection up to 3 times for reliability
        for _ in range(3):
            try:
                lang = langdetect.detect(text)
                if lang in CONFIG["SUPPORTED_LANGUAGES"]:
                    return lang
            except:
                pass
    except Exception as e:
        logger.error(f"Language detection error: {str(e)}")

    return 'en'

# ===== CONVERSATION MEMORY SYSTEM =====
class ConversationMemory:
    def __init__(self):
        self.sessions = {}
        self.last_cleanup = datetime.now()

    def start_session(self, thread_id, initial_prompt):
        lang = detect_language(initial_prompt)
        lang_specific_prompt = INITIAL_SYSTEM_PROMPT + LANGUAGE_INSTRUCTION
        self.sessions[thread_id] = {
            "history": [
                {"role": "system", "content": lang_specific_prompt},
                {"role": "user", "content": initial_prompt}
            ],
            "last_active": datetime.now(),
            "message_count": 0,
            "language": lang
        }
        return self.sessions[thread_id]

    def get_session(self, thread_id):
        self.cleanup()
        return self.sessions.get(thread_id)

    def add_exchange(self, thread_id, user_message, ai_response):
        if thread_id not in self.sessions:
            return False

        session = self.sessions[thread_id]
        session["history"].extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": ai_response}
        ])

        # Trim history while preserving system message
        if len(session["history"]) > CONFIG["MAX_HISTORY"] * 2 + 2:
            session["history"] = [session["history"][0]] + session["history"][-CONFIG["MAX_HISTORY"] * 2:]

        session["last_active"] = datetime.now()
        session["message_count"] += 1

        # Switch to follow-up mode after first response
        if session["message_count"] == 1:
            follow_up_prompt = FOLLOW_UP_SYSTEM_PROMPT + LANGUAGE_INSTRUCTION
            session["history"][0]["content"] = follow_up_prompt

        return True

    def cleanup(self):
        if (datetime.now() - self.last_cleanup) < timedelta(minutes=30):
            return

        for thread_id in list(self.sessions.keys()):
            session = self.sessions[thread_id]
            if (datetime.now() - session["last_active"]) > timedelta(hours=CONFIG["MEMORY_DURATION"]):
                del self.sessions[thread_id]
                logger.info(f"Cleaned up expired session: {thread_id}")

        self.last_cleanup = datetime.now()

# Initialize memory system
memory = ConversationMemory()

# ===== GLOBAL CONSTANTS =====
DISCLAIMER = "💬 *Remember: I'm an AI guide, not a licensed therapist. For clinical support, consult a professional*"

# ===== MULTILINGUAL SAFETY PROTOCOLS =====
def check_safety(message: str) -> bool:
    """Enhanced safety check with multilingual support"""
    message_lower = message.lower()
    return not any(
        flag in message_lower or 
        flag in translate_to_english(message_lower)
        for flag in CONFIG["CRISIS_KEYWORDS"]
    )

def crisis_response(lang: str = 'en') -> str:
    """Return crisis resources in user's language"""
    if lang in ERROR_TRANSLATIONS:
        return ERROR_TRANSLATIONS[lang]['crisis']
    return (
        "🚨 I'm concerned about what you're sharing. Please reach out immediately:\n"
        "• Crisis Text Line: Text HOME to 741741\n"
        "• International Help: https://www.iasp.info/resources/Crisis_Centres/\n"
        "• Your local emergency services"
    )

# ===== TRANSLATION HELPER =====
def translate_to_english(text: str) -> str:
    """Simple keyword translation for safety checks"""
    translations = {
        # Spanish
        "suicidio": "suicide",
        "suicidarse": "suicide",
        "autolesión": "self-harm",
        "matarme": "kill myself",
        "acabar con todo": "end it all",
        # French
        "suicide": "suicide",
        "me tuer": "kill myself",
        "automutilation": "self-harm",
        "tout arrêter": "end it all",
        # German
        "selbstmord": "suicide",
        "selbstverletzung": "self-harm",
        "mich umbringen": "kill myself",
        "alles beenden": "end it all",
        # Add more languages as needed
    }
    for foreign, english in translations.items():
        text = text.replace(foreign, english)
    return text

# ===== MULTILINGUAL RESPONSE GENERATION =====
def get_therapeutic_response(history: list, detected_lang: str) -> str:
    try:
        # Build Mixtral-compatible prompt
        prompt = ""
        for msg in history:
            if msg["role"] == "system":
                prompt += f"<s>[INST] {msg['content']} [/INST]"
            elif msg["role"] == "user":
                prompt += f"<s>[INST] {msg['content']} [/INST]"
            else:
                prompt += f"{msg['content']} </s><s>"

        # Add explicit language instruction for non-English
        if detected_lang != 'en':
            prompt += f"<s>[INST] Respond exclusively in {detected_lang} without using English. [/INST]"

        # Prepare API request
        headers = {"Authorization": f"Bearer {CONFIG['HF_API_KEY']}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 450,  # Increased for multilingual responses
                "temperature": 0.82,
                "top_p": 0.90,
                "repetition_penalty": 1.12,
                "return_full_text": False
            }
        }

        # Send request with detailed logging
        logger.info(f"Sending request to model: {CONFIG['MODEL']}")
        start_time = time.time()
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{CONFIG['MODEL']}",
            headers=headers,
            json=payload,
            timeout=90  # Increased timeout
        )
        elapsed = time.time() - start_time
        logger.info(f"Received response in {elapsed:.2f}s - Status: {response.status_code}")

        # Process response
        if response.status_code == 200:
            try:
                raw_response = response.json()[0]['generated_text'].strip()

                # Clean up any leftover tags
                raw_response = raw_response.replace('</s>', '').replace('<s>', '').strip()

                # Skip English empathy markers for non-English
                if detected_lang == 'en' and random.random() > 0.6:
                    human_element = random.choice(EMPATHY_MARKERS) + " "
                    return human_element + raw_response
                return raw_response

            except (KeyError, IndexError) as e:
                logger.error(f"Response parsing error: {str(e)} - JSON: {response.text}")
                # Return translated error message
                if detected_lang in ERROR_TRANSLATIONS:
                    return ERROR_TRANSLATIONS[detected_lang]['processing']
                return "🤔 I need a moment to process that. Could you rephrase or add more context?"
        else:
            logger.error(f"API Error: Status {response.status_code}, Response: {response.text}")
            if detected_lang in ERROR_TRANSLATIONS:
                return ERROR_TRANSLATIONS[detected_lang]['processing']
            return "🤔 I need a moment to process that. Could you rephrase or add more context?"

    except Exception as e:
        logger.error(f"Response error: {str(e)}", exc_info=True)
        if detected_lang in ERROR_TRANSLATIONS:
            return ERROR_TRANSLATIONS[detected_lang]['error']
        return "⚠️ My thoughts are tangled right now. Could we try again?"

# ===== DISCORD EVENT HANDLERS =====
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")
    try:
        server_id = discord.Object(id=CONFIG["SERVER_ID"])
        synced = await tree.sync(guild=server_id)
        logger.info(f"🌿 Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"❌ Command sync failed: {str(e)}")
    logger.info("🌿 Bot is ready!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not isinstance(message.channel, discord.Thread):
        return

    thread = message.channel
    session = memory.get_session(thread.id)

    if not session:
        return

    # Get detected language from session
    detected_lang = session.get('language', 'en')

    # Enhanced safety check
    if not check_safety(message.content):
        await thread.send(crisis_response(detected_lang))
        return

    # Add user message to history
    session["history"].append({"role": "user", "content": message.content})

    # Show typing indicator
    async with thread.typing():
        # Get AI response with language context
        response = get_therapeutic_response(session["history"], detected_lang)

        # Add to history and memory
        session["history"].append({"role": "assistant", "content": response})
        memory.add_exchange(thread.id, message.content, response)

        # Send response
        await thread.send(f"**Sol:** {response}\n\n{DISCLAIMER}")

@tree.command(name="sol", description="Start therapy session")
async def sol_command(interaction: discord.Interaction, issue: str):
    try:
        # Initial safety check
        if not check_safety(issue):
            await interaction.response.send_message(crisis_response('en'), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Create private therapy thread
        thread = await interaction.channel.create_thread(
            name=f"🌱 {interaction.user.name}'s Therapy Space",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )

        # Initialize conversation
        memory.start_session(thread.id, issue)
        session = memory.get_session(thread.id)
        detected_lang = session.get('language', 'en')

        # Show typing indicator
        async with thread.typing():
            # Get AI response with language context
            response = get_therapeutic_response(session["history"], detected_lang)
            session["history"].append({"role": "assistant", "content": response})
            memory.add_exchange(thread.id, issue, response)

            # Send initial response
            await thread.send(
                f"**Sol:** {response}\n\n"
                f"{DISCLAIMER}\n\n"
                "💬 **Simply reply here to continue our conversation naturally**"
            )

        await interaction.followup.send(
            f"🌿 Your safe space is ready in {thread.mention}!\n"
            "I'm here when you're ready to talk.",
            ephemeral=True
        )

    except Exception as e:
        logger.error(f"Command error: {str(e)}", exc_info=True)
        await interaction.followup.send(f"🌧️ Something went wrong: {str(e)}", ephemeral=True)
    import os
    import threading
    from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Sol-CBT Bot Running", 200

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 7860)))

# 在 bot.run() 前添加
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# 启动 Discord Bot
bot.run(os.getenv('DISCORD_TOKEN'))
        
logger.info("=== BOT STARTING ===")
# ===== START BOT =====
if __name__ == "__main__":
    logger.info("=== STARTING MULTILINGUAL SOL THERAPY BOT ===")
    logger.info(f"Using Model: {CONFIG['MODEL']}")
    logger.info(f"Supported Languages: {', '.join(CONFIG['SUPPORTED_LANGUAGES'])}")
    bot.run(CONFIG["DISCORD_TOKEN"])
