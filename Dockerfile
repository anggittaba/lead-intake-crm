# Online demo image: FastAPI CRM + built-in engine (no n8n inside). Works on Hugging Face Spaces (port 7860) and Render.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi==0.115.14 uvicorn==0.54.0 Jinja2==3.1.6 python-multipart==0.0.20 httpx==0.28.1
COPY leadcrm ./leadcrm
COPY data ./data
RUN useradd -m app && mkdir -p /app/var && chown -R app /app
USER app
ENV HOST=0.0.0.0 PORT=7860 CRM_DB=/app/var/crm.sqlite
EXPOSE 7860
CMD ["sh", "-c", "uvicorn leadcrm.app:app --host $HOST --port $PORT"]
