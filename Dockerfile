FROM python:3.11-slim
WORKDIR /app
COPY app.py bot.py ./
ENV PYTHONUNBUFFERED=1
EXPOSE 10000
CMD ["python", "app.py"]
