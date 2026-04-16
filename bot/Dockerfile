FROM python:3.11-slim
RUN useradd --create-home --shell /bin/bash botuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY telemt-bot.py .
RUN mkdir -p /app/logs && chown -R botuser:botuser /app
USER botuser
CMD ["python3", "telemt-bot.py"]
