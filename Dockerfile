FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p downloads && useradd -m appuser && chown -R appuser:appuser /app
USER appuser
ENV PORT=8000
EXPOSE 8000
CMD ["sh","-c","gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 3600 app:app"]
