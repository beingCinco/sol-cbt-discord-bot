FROM python:3.10-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# 必须使用 7860 端口（Hugging Face 要求）
CMD python -u bot.py --port 7860
