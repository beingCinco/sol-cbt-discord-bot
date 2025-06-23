import os
import discord
import logging
from flask import Flask
import threading

# 基础配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sol-therapy-bot')

# 环境变量
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = os.getenv('SERVER_ID')

# 验证环境变量
if not DISCORD_TOKEN or not SERVER_ID:
    logger.error("Missing required environment variables")
    exit(1)

# Flask 应用
app = Flask(__name__)

@app.route('/')
def home():
    return "Sol-CBT Bot Running", 200

@app.route('/health')
def health_check():
    return "OK", 200

# Discord 机器人
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message):
        await message.channel.send(f"Hello {message.author.mention}! I'm running :)")

# 线程函数
def run_flask():
    app.run(host='0.0.0.0', port=7860)

def run_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    logger.info("=== Starting SOL Therapy Bot ===")
    
    # 启动 Flask 线程
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started")
    
    # 启动 Discord 机器人
    try:
        run_bot()
    except Exception as e:
        logger.critical(f"Bot startup failed: {str(e)}")
