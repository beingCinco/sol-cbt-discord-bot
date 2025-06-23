import os
import discord
from discord import app_commands
import requests
import time
import logging
from datetime import datetime, timedelta
import random
import langdetect
import threading
from flask import Flask, request
import sys

# ===== 新增 Flask 服务器设置 =====
app = Flask(__name__)

@app.route('/')
def home():
    """健康检查端点"""
    return "Sol-CBT Bot Running", 200

@app.route('/health')
def health_check():
    """详细的健康检查端点"""
    return {
        "status": "running",
        "bot": "online" if bot.is_ready() else "offline",
        "memory_sessions": len(memory.sessions),
        "last_cleanup": str(memory.last_cleanup)
    }, 200

@app.route('/logs')
def view_logs():
    """查看最近的日志"""
    try:
        with open('debug.log', 'r') as f:
            logs = f.read()
        return f"<pre>{logs}</pre>", 200
    except Exception as e:
        return f"Error reading logs: {str(e)}", 500

# ===== 新增 Keep-Alive 机制 =====
def keep_alive():
    """防止 Hugging Face 容器休眠"""
    while True:
        try:
            # 获取 Space 名称（在 Hugging Face Spaces 中自动设置）
            space_name = os.getenv('SPACE_NAME', 'default-space')
            space_url = f"https://{space_name}.hf.space"
            
            # 同时调用健康检查端点
            requests.get(space_url)
            requests.get(f"{space_url}/health")
            
            logger.info(f"Keep-alive request sent to {space_url}")
        except Exception as e:
            logger.error(f"Keep-alive error: {str(e)}")
        time.sleep(300)  # 每 5 分钟唤醒一次

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('debug.log')
    ]
)
logger = logging.getLogger('discord')

# ===== 配置从环境变量获取 =====
CONFIG = {
    "DISCORD_TOKEN": os.getenv('DISCORD_TOKEN', 'default_token'),
    "SERVER_ID": os.getenv('SERVER_ID', 'default_server'),
    "HF_API_KEY": os.getenv('HF_API_TOKEN', 'default_api_key'),   
    "MODEL": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "CRISIS_KEYWORDS": ["suicide", "self-harm", "kill myself", "end it all"],
    "MEMORY_DURATION": 24,
    "MAX_HISTORY": 6,
    "SUPPORTED_LANGUAGES": ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja']
}

# ===== 语言配置 =====
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
    # 其他语言...
}

# ===== 治疗提示 =====
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

# ===== 治疗师人格元素 =====
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

# ===== Discord 机器人设置 =====
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ===== 语言检测 =====
def detect_language(text: str) -> str:
    """鲁棒的语言检测"""
    if not text.strip():
        return 'en'

    try:
        # 尝试多次检测以提高可靠性
        for _ in range(3):
            try:
                lang = langdetect.detect(text)
                if lang in CONFIG["SUPPORTED_LANGUAGES"]:
                    return lang
            except:
                pass
    except Exception as e:
        logger.error(f"语言检测错误: {str(e)}")

    return 'en'

# ===== 对话记忆系统 =====
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

        # 修剪历史记录，保留系统消息
        if len(session["history"]) > CONFIG["MAX_HISTORY"] * 2 + 2:
            session["history"] = [session["history"][0]] + session["history"][-CONFIG["MAX_HISTORY"] * 2:]

        session["last_active"] = datetime.now()
        session["message_count"] += 1

        # 第一次响应后切换到后续模式
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
                logger.info(f"清理过期会话: {thread_id}")

        self.last_cleanup = datetime.now()

# 初始化记忆系统
memory = ConversationMemory()

# ===== 全局常量 =====
DISCLAIMER = "💬 *记住：我是AI向导，不是持证治疗师。如需临床支持，请咨询专业人士*"

# ===== 多语言安全协议 =====
def check_safety(message: str) -> bool:
    """增强的多语言安全检查"""
    message_lower = message.lower()
    return not any(
        flag in message_lower or 
        flag in translate_to_english(message_lower)
        for flag in CONFIG["CRISIS_KEYWORDS"]
    )

def crisis_response(lang: str = 'en') -> str:
    """返回用户语言的危机资源"""
    if lang in ERROR_TRANSLATIONS:
        return ERROR_TRANSLATIONS[lang]['crisis']
    return (
        "🚨 我担心你分享的内容。请立即联系：\n"
        "• 危机短信热线：发送HOME到741741\n"
        "• 国际帮助：https://www.iasp.info/resources/Crisis_Centres/\n"
        "• 当地紧急服务"
    )

# ===== 翻译辅助 =====
def translate_to_english(text: str) -> str:
    """安全检查的简单关键词翻译"""
    translations = {
        # 西班牙语
        "suicidio": "suicide",
        "suicidarse": "suicide",
        "autolesión": "self-harm",
        "matarme": "kill myself",
        "acabar con todo": "end it all",
        # 法语
        "suicide": "suicide",
        "me tuer": "kill myself",
        "automutilation": "self-harm",
        "tout arrêter": "end it all",
        # 德语
        "selbstmord": "suicide",
        "selbstverletzung": "self-harm",
        "mich umbringen": "kill myself",
        "alles beenden": "end it all",
        # 添加更多语言...
    }
    for foreign, english in translations.items():
        text = text.replace(foreign, english)
    return text

# ===== 多语言响应生成 =====
def get_therapeutic_response(history: list, detected_lang: str) -> str:
    try:
        # 构建Mixtral兼容提示
        prompt = ""
        for msg in history:
            if msg["role"] == "system":
                prompt += f"<s>[INST] {msg['content']} [/INST]"
            elif msg["role"] == "user":
                prompt += f"<s>[INST] {msg['content']} [/INST]"
            else:
                prompt += f"{msg['content']} </s><s>"

        # 为非英语添加明确语言指令
        if detected_lang != 'en':
            prompt += f"<s>[INST] Respond exclusively in {detected_lang} without using English. [/INST]"

        # 准备API请求
        headers = {"Authorization": f"Bearer {CONFIG['HF_API_KEY']}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 450,  # 为多语言响应增加
                "temperature": 0.82,
                "top_p": 0.90,
                "repetition_penalty": 1.12,
                "return_full_text": False
            }
        }

        # 发送请求并详细记录
        logger.info(f"发送请求到模型: {CONFIG['MODEL']}")
        start_time = time.time()
        
        # 使用更可靠的请求方法
        try:
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{CONFIG['MODEL']}",
                headers=headers,
                json=payload,
                timeout=90
            )
        except requests.exceptions.Timeout:
            logger.warning("API请求超时，重试中...")
            response = requests.post(
                f"https://api-inference.huggingface.co/models/{CONFIG['MODEL']}",
                headers=headers,
                json=payload,
                timeout=120
            )
        
        elapsed = time.time() - start_time
        logger.info(f"收到响应时间: {elapsed:.2f}s - 状态: {response.status_code}")

        # 处理响应
        if response.status_code == 200:
            try:
                raw_response = response.json()[0]['generated_text'].strip()

                # 清理残留标签
                raw_response = raw_response.replace('</s>', '').replace('<s>', '').strip()

                # 非英语跳过英语共情标记
                if detected_lang == 'en' and random.random() > 0.6:
                    human_element = random.choice(EMPATHY_MARKERS) + " "
                    return human_element + raw_response
                return raw_response

            except (KeyError, IndexError) as e:
                logger.error(f"响应解析错误: {str(e)} - JSON: {response.text}")
                # 返回翻译的错误消息
                if detected_lang in ERROR_TRANSLATIONS:
                    return ERROR_TRANSLATIONS[detected_lang]['processing']
                return "🤔 我需要一点时间处理。你能重新表述或添加上下文吗？"
        else:
            logger.error(f"API错误: 状态 {response.status_code}, 响应: {response.text}")
            if detected_lang in ERROR_TRANSLATIONS:
                return ERROR_TRANSLATIONS[detected_lang]['processing']
            return "🤔 我需要一点时间处理。你能重新表述或添加上下文吗？"

    except Exception as e:
        logger.error(f"响应错误: {str(e)}", exc_info=True)
        if detected_lang in ERROR_TRANSLATIONS:
            return ERROR_TRANSLATIONS[detected_lang]['error']
        return "⚠️ 我的思绪现在有些混乱。我们能再试一次吗？"

# ===== Discord 事件处理器 =====
@bot.event
async def on_ready():
    logger.info(f"✅ 登录为 {bot.user}")
    try:
        server_id = discord.Object(id=CONFIG["SERVER_ID"])
        synced = await tree.sync(guild=server_id)
        logger.info(f"🌿 同步 {len(synced)} 个命令")
    except Exception as e:
        logger.error(f"❌ 命令同步失败: {str(e)}")
    logger.info("🌿 机器人已就绪！")

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

    # 从会话获取检测到的语言
    detected_lang = session.get('language', 'en')

    # 增强安全检查
    if not check_safety(message.content):
        await thread.send(crisis_response(detected_lang))
        return

    # 添加用户消息到历史
    session["history"].append({"role": "user", "content": message.content})

    # 显示输入指示器
    async with thread.typing():
        # 获取带语言上下文的AI响应
        response = get_therapeutic_response(session["history"], detected_lang)

        # 添加到历史和记忆
        session["history"].append({"role": "assistant", "content": response})
        memory.add_exchange(thread.id, message.content, response)

        # 发送响应
        await thread.send(f"**Sol:** {response}\n\n{DISCLAIMER}")

@tree.command(name="sol", description="开始治疗会话")
async def sol_command(interaction: discord.Interaction, issue: str):
    try:
        # 初始安全检查
        if not check_safety(issue):
            await interaction.response.send_message(crisis_response('en'), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # 创建私密治疗线程
        thread = await interaction.channel.create_thread(
            name=f"🌱 {interaction.user.name}的治疗空间",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )

        # 初始化对话
        memory.start_session(thread.id, issue)
        session = memory.get_session(thread.id)
        detected_lang = session.get('language', 'en')

        # 显示输入指示器
        async with thread.typing():
            # 获取带语言上下文的AI响应
            response = get_therapeutic_response(session["history"], detected_lang)
            session["history"].append({"role": "assistant", "content": response})
            memory.add_exchange(thread.id, issue, response)

            # 发送初始响应
            await thread.send(
                f"**Sol:** {response}\n\n"
                f"{DISCLAIMER}\n\n"
                "💬 **直接在这里回复即可继续我们的自然对话**"
            )

        await interaction.followup.send(
            f"🌿 你的安全空间已在 {thread.mention} 准备就绪！\n"
            "当你准备好交谈时，我就在这里。",
            ephemeral=True
        )

    except Exception as e:
        logger.error(f"命令错误: {str(e)}", exc_info=True)
        await interaction.followup.send(f"🌧️ 出了点问题: {str(e)}", ephemeral=True)

# ===== 主启动逻辑 =====
def run_flask():
    """在单独线程中运行Flask服务器"""
    port = int(os.getenv('PORT', 7860))
    logger.info(f"启动Flask服务器在端口 {port}")
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    logger.info("=== 启动多语言SOL治疗机器人 ===")
    logger.info(f"使用模型: {CONFIG['MODEL']}")
    logger.info(f"支持语言: {', '.join(CONFIG['SUPPORTED_LANGUAGES']}")
    
    # 验证环境变量
    required_envs = ['DISCORD_TOKEN', 'HF_API_TOKEN', 'SERVER_ID']
    missing = [env for env in required_envs if not os.getenv(env)]
    
    if missing:
        logger.error(f"缺少关键环境变量: {', '.join(missing)}")
        sys.exit(1)
    
    # 启动keep-alive线程
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    logger.info("Keep-alive线程已启动")
    
    # 启动Flask服务器线程
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info("Flask服务器线程已启动")
    
    # 启动Discord机器人
    try:
        bot.run(CONFIG["DISCORD_TOKEN"])
    except Exception as e:
        logger.critical(f"机器人启动失败: {str(e)}", exc_info=True)
        # 在Hugging Face Spaces中记录错误后退出
        sys.exit(1)
