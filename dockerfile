FROM python:3.10-slim

# 安全设置
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR off

# 创建非root用户
RUN groupadd -r sol && useradd -r -g sol sol
USER sol

WORKDIR /app
COPY --chown=sol:sol . .

# 安全安装依赖
RUN pip install --user --no-cache-dir -r requirements.txt

EXPOSE 7860

CMD ["python", "main.py"]
