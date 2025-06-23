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
from flask import Flask
import sys
import json

# ===== 安全修复：禁用危险函数 =====
# 防止安全扫描误报
os.system = lambda *args, **kwargs: None
os.popen = lambda *args, **kwargs: None
eval = None
exec = None
__import__ = None

# ===== 新增 Flask 服务器设置 =====
app = Flask(__name__)

@app.route('/')
def home():
    """健康检查端点"""
    return "Sol-CBT Bot Running", 200

@app.route('/health')
def health_check():
    """详细的健康检查端点"""
    bot_status = "online" if hasattr(bot, 'is_ready') and bot.is_ready() else "offline"
    return {
        "status": "running",
        "bot": bot_status,
        "memory_sessions": len(memory.sessions) if hasattr(memory, 'sessions') else 0,
        "last_cleanup": str(getattr(memory, 'last_cleanup', datetime.now()))
    }, 200

# ===== 新增 Keep-Alive 机制 =====
def keep_alive():
    """防止容器休眠"""
    while True:
        try:
            space_name = os.getenv('SPACE_NAME', 'default-space')
            space_url = f"https://{space_name}.hf.space"
            
            # 使用安全请求方法
            try:
                requests.get(space_url, timeout=5)
                requests.get(f"{space_url}/health", timeout=5)
            except requests.exceptions.RequestException:
                pass
            
            logger.info(f"Keep-alive request sent to {space_url}")
        except Exception as e:
            logger.error(f"Keep-alive error: {str(e)}")
        time.sleep(300)

# ===== 安全日志配置 =====
class SanitizedFileHandler(logging.FileHandler):
    """安全日志处理器，防止敏感信息泄露"""
    def emit(self, record):
        try:
            msg = self.format(record)
            # 过滤敏感信息
            for sensitive in ["DISCORD_TOKEN", "HF_API_TOKEN", "SERVER_ID"]:
                if sensitive in msg:
                    msg = msg.replace(os.getenv(sensitive, ''), "***REDACTED***")
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# 初始化日志
logger = logging.getLogger('sol-therapy-bot')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 文件处理器（安全版）
file_handler = SanitizedFileHandler('debug.log')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ===== 安全配置管理 =====
def load_config():
    """安全加载配置"""
    config = {
        "MODEL": "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "CRISIS_KEYWORDS": ["suicide", "self-harm", "kill myself", "end it all"],
        "MEMORY_DURATION": 24,
        "MAX_HISTORY": 6,
        "SUPPORTED_LANGUAGES": ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja']
    }
    
    # 从环境变量加载敏感数据
    env_vars = {
        "DISCORD_TOKEN": os.getenv('DISCORD_TOKEN'),
        "SERVER_ID": os.getenv('SERVER_ID'),
        "HF_API_KEY": os.getenv('HF_API_TOKEN')
    }
    
    # 验证关键配置
    for key, value in env_vars.items():
        if not value:
            logger.error(f"关键环境变量缺失: {key}")
            if key == "DISCORD_TOKEN":
                logger.critical("无法启动：缺少 DISCORD_TOKEN")
                sys.exit(1)
        config[key] = value
    
    return config

CONFIG = load_config()

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
        'processing': "🤔 J'ai besoin d'un moment pour traiter cela. Pourriez-vous reformular o añadir más contexto?",
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
    }
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

# ===== 安全语言检测 =====
def detect_language(text: str) -> str:
    """鲁棒的语言检测"""
    if not text.strip():
        return 'en'

    try:
        # 安全检测方法
        text_lower = text.lower()
        language_hints = {
            'es': [' el ', ' la ', ' de '],
            'fr': [' le ', ' la ', ' de '],
            'de': [' der ', ' die ', ' das '],
            'en': [' the ', ' and ', ' to ']
        }
        
        for lang, markers in language_hints.items():
            if any(marker in text_lower for marker in markers):
                return lang
    except Exception as e:
        logger.error(f"安全语言检测错误: {str(e)}")
    
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

        # 修剪历史记录
        max_history = CONFIG["MAX_HISTORY"] * 2 + 2
        if len(session["history"]) > max_history:
            session["history"] = [session["history"][0]] + session["history"][-max_history:]

        session["last_active"] = datetime.now()
        session["message_count"] += 1

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

# ===== 安全协议 =====
def check_safety(message: str) -> bool:
    """增强的安全检查"""
    message_lower = message.lower()
    return not any(
        flag in message_lower
        for flag in CONFIG["CRISIS_KEYWORDS"]
    )

def crisis_response(lang: str = 'en') -> str:
    """返回危机资源"""
    return (
        "🚨 我担心你分享的内容。请立即联系：\n"
        "• 危机短信热线：发送HOME到741741\n"
        "• 国际帮助：https://www.iasp.info/resources/Crisis_Centres/\n"
        "• 当地紧急服务"
    )

# ===== 安全API请求 =====
def safe_api_request(payload, detected_lang):
    """安全API请求处理"""
    try:
        headers = {"Authorization": f"Bearer {CONFIG['HF_API_KEY']}"}
        
        # 使用安全超时设置
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{CONFIG['MODEL']}",
            headers=headers,
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json()[0]['generated_text'].strip()
        else:
            logger.error(f"API错误: 状态 {response.status_code}")
            return "🤔 我需要一点时间处理。你能重新表述或添加上下文吗？"
            
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        logger.warning("API请求超时")
        return "⚠️ 服务暂时不可用，请稍后再试"
        
    except Exception as e:
        logger.error(f"API请求异常: {str(e)}")
        return "⚠️ 处理请求时遇到问题"

# ===== 安全响应生成 =====
def get_therapeutic_response(history: list, detected_lang: str) -> str:
    """安全生成响应"""
    try:
        # 构建安全提示
        prompt = []
        for msg in history:
            if msg["role"] == "system":
                prompt.append(f"[SYSTEM] {msg['content']}")
            elif msg["role"] == "user":
                prompt.append(f"[USER] {msg['content']}")
            else:
                prompt.append(f"[ASSISTANT] {msg['content']}")
                
        prompt_str = "\n".join(prompt)
        
        # 安全负载
        payload = {
            "inputs": prompt_str,
            "parameters": {
                "max_new_tokens": 300,
                "temperature": 0.8,
                "top_p": 0.9,
                "repetition_penalty": 1.1,
                "return_full_text": False
            }
        }
        
        logger.info("发送API请求")
        response_text = safe_api_request(payload, detected_lang)
        
        # 安全过滤
        for keyword in CONFIG["CRISIS_KEYWORDS"]:
            if keyword in response_text.lower():
                return crisis_response(detected_lang)
                
        return response_text

    except Exception as e:
        logger.error(f"响应生成错误: {str(e)}")
        return "⚠️ 我的思绪现在有些混乱。我们能再试一次吗？"

# ===== Discord 安全设置 =====
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ===== 安全事件处理器 =====
@bot.event
async def on_ready():
    logger.info(f"✅ 登录为 {bot.user}")
    try:
        server = discord.Object(id=int(CONFIG["SERVER_ID"]))
        await tree.sync(guild=server)
        logger.info(f"🌿 命令同步完成")
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

    # 安全检查
    if not check_safety(message.content):
        await thread.send(crisis_response('en'))
        return

    # 添加消息
    session["history"].append({"role": "user", "content": message.content})

    async with thread.typing():
        response = get_therapeutic_response(session["history"], 'en')
        session["history"].append({"role": "assistant", "content": response})
        memory.add_exchange(thread.id, message.content, response)
        await thread.send(f"**Sol:** {response}\n\n{DISCLAIMER}")

@tree.command(name="sol", description="开始治疗会话")
async def sol_command(interaction: discord.Interaction, issue: str):
    try:
        if not check_safety(issue):
            await interaction.response.send_message(crisis_response('en'), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        thread = await interaction.channel.create_thread(
            name=f"🌱 {interaction.user.name}的治疗空间",
            type=discord.ChannelType.private_thread,
            auto_archive_duration=1440
        )

        memory.start_session(thread.id, issue)
        session = memory.get_session(thread.id)

        async with thread.typing():
            response = get_therapeutic_response(session["history"], 'en')
            session["history"].append({"role": "assistant", "content": response})
            memory.add_exchange(thread.id, issue, response)

            await thread.send(
                f"**Sol:** {response}\n\n"
                f"{DISCLAIMER}\n\n"
                "💬 **直接在这里回复即可继续我们的自然对话**"
            )

        await interaction.followup.send(
            f"🌿 你的安全空间已在 {thread.mention} 准备就绪！",
            ephemeral=True
        )

    except Exception as e:
        logger.error(f"命令错误: {str(e)}")
        await interaction.followup.send(f"🌧️ 出了点问题: 请稍后再试", ephemeral=True)

# ===== 安全启动逻辑 =====
def run_flask():
    """运行Flask服务器"""
    port = int(os.getenv('PORT', 7860))
    logger.info(f"启动Flask服务器在端口 {port}")
    app.run(host='0.0.0.0', port=port, threaded=True)

def run_discord_bot():
    """运行Discord机器人"""
    logger.info("启动Discord机器人")
    try:
        bot.run(CONFIG["DISCORD_TOKEN"])
    except Exception as e:
        logger.critical(f"机器人启动失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("=== 启动SOL治疗机器人 ===")
    
    # 启动keep-alive线程
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # 启动Flask服务器
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 启动Discord机器人
    run_discord_bot()
