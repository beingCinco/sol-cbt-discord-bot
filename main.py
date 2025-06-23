import os
import discord
import requests
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
HF_API_TOKEN = os.getenv('HF_API_TOKEN')
SERVER_ID = os.getenv('SERVER_ID')

# 验证环境变量
if not DISCORD_TOKEN or not HF_API_TOKEN or not SERVER_ID:
    logger.error("缺少必要的环境变量")
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
    logger.info(f"✅ 登录为 {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # 简单响应测试
    if bot.user.mentioned_in(message):
        await message.channel.send(f"你好 {message.author.mention}！我正在运行 :)")

# 线程函数
def run_flask():
    app.run(host='0.0.0.0', port=7860)

def run_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    logger.info("=== 启动 SOL 治疗机器人 ===")
    
    # 启动 Flask 线程
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask 服务器已启动")
    
    # 启动 Discord 机器人
    try:
        run_bot()
    except Exception as e:
        logger.critical(f"机器人启动失败: {str(e)}")
