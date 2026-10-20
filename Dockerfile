FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY groot_share/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -r groot && useradd -r -g groot -d /home/groot groot
RUN mkdir -p /config /tmp/groot_uploads /storage && chown groot:groot /config /tmp/groot_uploads /storage

COPY groot_share/app /app/app
COPY groot_share/templates /app/templates
COPY groot_share/static /app/static

RUN chmod -R 755 /app/static /app/templates /app/app
RUN chown -R groot:groot /app /config /tmp/groot_uploads /storage

USER groot

ENV APP_HOST=0.0.0.0
ENV APP_PORT=8080
ENV CONFIG_PATH=/config/storages.json
ENV MAX_UPLOAD_SIZE_MB=2048
ENV ADMIN_PASSWORD=admin
ENV SESSION_SECRET=change-me-in-production
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f -s http://localhost:8080/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]