import discord
from discord.ext import commands, tasks
from huggingface_hub import InferenceClient
import os
from dotenv import load_dotenv
from cachetools import TTLCache
import logging
from asyncio import Queue
import asyncio

# 设置日志
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# 加载环境变量
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

# 验证环境变量
if not DISCORD_TOKEN or not HUGGINGFACE_API_KEY:
    logging.error("缺少 DISCORD_TOKEN 或 HUGGINGFACE_API_KEY")
    raise ValueError("缺少 DISCORD_TOKEN 或 HUGGINGFACE_API_KEY")

# 初始化机器人和 API 客户端
bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
client = InferenceClient(model="mistralai/Mixtral-8x7B-Instruct-v0.1", token=HUGGINGFACE_API_KEY)
cache = TTLCache(maxsize=1000, ttl=3600)  # 缓存 1 小时
request_queue = Queue()

# 异步请求处理
async def process_requests():
    while True:
        ctx, user_input = await request_queue.get()
        try:
            if user_input in cache:
                await ctx.send(cache[user_input])
                logging.info(f"用户 {ctx.author.id} 使用缓存响应：{user_input}")
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
            response = client.text_generation(
                prompt=prompt,
                max_new_tokens=150,
                temperature=0.7
            )
            cache[user_input] = response
            await ctx.send(response)
            logging.info(f"用户 {ctx.author.id} 输入：{user_input}，响应：{response}")
        except Exception as e:
            await ctx.send("抱歉，处理时出错，请稍后再试！")
            logging.error(f"处理用户 {ctx.author.id} 输入 {user_input} 时出错：{e}")
        request_queue.task_done()

# 启动时事件
@bot.event
async def on_ready():
    print(f"{bot.user} 已上线！")
    logging.info(f"{bot.user} 已上线！")
    asyncio.create_task(process_requests())  # 启动请求处理

# CBT 指令
@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)  # 每用户每分钟 1 次
async def cbt(ctx, *, user_input):
    await request_queue.put((ctx, user_input))
    logging.info(f"用户 {ctx.author.id} 发起 CBT 请求：{user_input}")

# 保持活跃（防止 Space 休眠）
@tasks.loop(minutes=20)
async def keep_alive():
    logging.info("保持 Space 活跃")

# 错误处理
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"请等待 {int(error.retry_after)} 秒后再试！")
    else:
        await ctx.send("发生错误，请稍后再试！")
        logging.error(f"命令错误：{error}")

# 启动机器人
bot.run(DISCORD_TOKEN)
