import sys
import os
import discord
import logging
import asyncio
import threading
from discord import app_commands
import subprocess

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('sol-therapy-bot')

# 调试：检查关键模块是否存在
try:
    import gradio
    import transformers
    import torch
    logger.info("✅ 关键依赖已安装")
except ImportError as e:
    logger.error(f"❌ 缺少关键模块: {e}")
    logger.info("### 已安装的包 ###")
    subprocess.run(["pip", "list"])
    sys.exit(1)

# Discord 配置
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# 确保立即响应命令
@tree.command(name="sol", description="开始治疗会话")
async def sol_command(interaction: discord.Interaction):
    try:
        # 立即响应以避免超时
        await interaction.response.defer(ephemeral=True)
        
        # 模拟处理时间
        await asyncio.sleep(1)
        
        # 发送实际响应
        await interaction.followup.send("🌿 你好！这是 Sol-CBT 治疗机器人的响应")
    except Exception as e:
        logger.error(f"命令处理错误: {str(e)}")
        await interaction.followup.send("⚠️ 处理命令时出错，请稍后再试")

@bot.event
async def on_ready():
    logger.info(f"✅ 已登录为 {bot.user}")
    try:
        # 获取服务器 ID
        server_id = int(os.getenv('SERVER_ID'))
        server = discord.Object(id=server_id)
        
        # 同步命令
        await tree.sync(guild=server)
        logger.info(f"🌿 已同步命令到服务器 {server_id}")
    except Exception as e:
        logger.error(f"❌ 命令同步失败: {str(e)}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # 确保机器人被提及时才响应
    if bot.user.mentioned_in(message):
        try:
            # 发送打字指示器
            async with message.channel.typing():
                await asyncio.sleep(1)  # 模拟处理时间
                
            # 发送响应
            await message.reply(f"你好 {message.author.mention}! 我是 Sol-CBT 治疗机器人，随时为您服务 🌱")
        except Exception as e:
            logger.error(f"消息处理错误: {str(e)}")

if __name__ == "__main__":
    # 验证环境变量
    required_envs = ['DISCORD_TOKEN', 'SERVER_ID']
    missing_envs = [env for env in required_envs if not os.getenv(env)]
    
    if missing_envs:
        logger.critical(f"❌ 缺少环境变量: {', '.join(missing_envs)}")
        logger.critical("请确保设置了以下环境变量:")
        for env in required_envs:
            logger.critical(f" - {env}")
        sys.exit(1)
    
    logger.info("=== 启动 SOL 治疗机器人 ===")
    
    # 启动 Discord 机器人
    try:
        bot_token = os.getenv('DISCORD_TOKEN')
        server_id = os.getenv('SERVER_ID')
        
        if not bot_token:
            logger.critical("❌ 错误: DISCORD_TOKEN 环境变量未设置")
            sys.exit(1)
            
        if not server_id:
            logger.critical("❌ 错误: SERVER_ID 环境变量未设置")
            sys.exit(1)
            
        logger.info(f"🤖 使用令牌启动 Discord 机器人: {bot_token[:5]}...{bot_token[-5:]}")
        logger.info(f"🏠 服务器 ID: {server_id}")
        
        bot.run(bot_token)
    except discord.LoginFailure:
        logger.critical("Discord 登录失败: 令牌可能无效")
    except Exception as e:
        logger.critical(f"机器人启动失败: {str(e)}")
