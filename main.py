import os
import discord
import logging
import threading
from flask import Flask

# 基础配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sol-therapy-bot')

# 环境变量验证
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN 未设置!")
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
    logger.info(f"已登录为 {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message):
        await message.channel.send(f"你好 {message.author.mention}! 我正在运行 :)")

# 线程函数
def run_flask():
    app.run(host='0.0.0.0', port=7860)

if __name__ == "__main__":
    logger.info("=== 启动 SOL 治疗机器人 ===")
    
    # 启动 Flask 线程
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask 服务器已启动")
    
    # 启动 Discord 机器人
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"机器人启动失败: {str(e)}")
