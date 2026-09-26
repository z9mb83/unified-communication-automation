# One image for uca-api, uca-webhooks and uca-workers (role chosen by UCA_SERVICE_ROLE).
# The existing email-sender image is built separately from services/email/Dockerfile
# and is NOT rebuilt or redeployed by this repository's pipelines.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    RUNTIME_ENV=cloud_run \
    STATE_BACKEND=firestore \
    UCA_STORE_BACKEND=firestore \
    UCA_QUEUE_BACKEND=cloudtasks

WORKDIR /srv
COPY requirements.txt ./
COPY services/email/requirements.txt services/email/requirements.txt
RUN pip install -r requirements.txt

COPY shared/ shared/
COPY services/ services/
COPY scripts/ scripts/
COPY config/*.example.yaml config/

RUN useradd --system --uid 10001 uca && chown -R uca /srv
USER uca

# Cloud Run sets $PORT
CMD ["sh", "-c", "exec uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --no-server-header"]
