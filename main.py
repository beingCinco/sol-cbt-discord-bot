import os
import logging
import sys
import discord
from discord.ext import commands, tasks
from huggingface_hub import InferenceClient
from cachetools import TTLCache
from asyncio import Queue
import asyncio
from requests.exceptions import RequestException

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load environment variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# Debug environment variables
logger.info(f"DISCORD_TOKEN is set: {'set' if DISCORD_TOKEN else 'unset'}")
logger.info(f"HUGGINGFACE_API_KEY is set: {'set' if HUGGINGFACE_API_KEY else 'unset'}")

# Validate environment variables
if not DISCORD_TOKEN or not HUGGINGFACE_API_KEY:
    logger.error("缺少 DISCORD_TOKEN 或 HUGGINGFACE_API_KEY")
    if os.getenv("CI") == "true":
        logger.info("Running in CI environment, skipping bot startup")
        sys.exit(0)  # Exit gracefully in CI
    raise ValueError("缺少 DISCORD_TOKEN 或 HUGGINGFACE_API_KEY")

# Initialize bot and API client
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix="!", intents=intents)
client = InferenceClient(model="mistralai/Mixtral-8x7B-Instruct-v0.1", token=HUGGINGFACE_API_KEY)
cache = TTLCache(maxsize=2000, ttl=3600)  # Increased cache for 500 users
request_queue = Queue()

# Asynchronous request processing
async def process_requests():
    while True:
        ctx, user_input = await request_queue.get()
        try:
            if user_input in cache:
                await ctx.send(cache[user_input])
                logger.info(f"用户 {ctx.author.id} 使用缓存响应：{user_input}")
                request_queue.task_done()
                continue

            prompt = f"""
            你是一个经过认知行为疗法（CBT）训练的心理咨询师。用户表达了以下情绪或问题：{user_input}。
            请按照以下步骤回应：
            1. 共情：表达对用户感受的理解。
            2. 识别：指出可能的负面思维模式。
            3. 挑战：提出质疑负面思维的证据。
            4. 替代：建议更积极的思维方式。
            回答简洁，语气温暖，控制在 150 字以内。
            """
            for attempt in range(3):  # Retry logic for API calls
                try:
                    response = client.text_generation(
                        prompt=prompt,
                        max_new_tokens=150,
                        temperature=0.7
                    )
                    cache[user_input] = response
                    await ctx.send(response)
                    logger.info(f"用户 {ctx.author.id} 输入：{user_input}，响应：{response}")
                    break
                except RequestException as e:
                    if attempt == 2:
                        await ctx.send("API 错误，请稍后再试！")
                        logger.error(f"API call failed for 用户 {ctx.author.id}: {e}")
                        break
                    await asyncio.sleep(2)
        except Exception as e:
            await ctx.send("抱歉，处理时出错，请稍后再试！")
            logger.error(f"处理用户 {ctx.author.id} 输入 {user_input} 时出错：{e}")
        request_queue.task_done()

# Bot ready event
@bot.event
async def on_ready():
    logger.info(f"{bot.user} 已上线！")
    asyncio.create_task(process_requests())  # Start request processing

# CBT command with cooldown
@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)  # 1 call per minute per user
async def cbt(ctx, *, user_input):
    await request_queue.put((ctx, user_input))
    logger.info(f"用户 {ctx.author.id} 发起 CBT 请求：{user_input}")

# Keep-alive task to prevent Space sleep
@tasks.loop(minutes=20)
async def keep_alive():
    logger.info("保持 Space 活跃")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"请等待 {int(error.retry_after)} 秒后再试！")
    else:
        await ctx.send("发生错误，请稍后再试！")
        logger.error(f"命令错误：{error}")

# Start bot (skip in CI)
if os.getenv("CI") != "true":
    keep_alive.start()  # Start keep-alive task
    bot.run(DISCORD_TOKEN)
else:
    logger.info("CI environment detected, skipping bot.run")
    sys.exit(0)
