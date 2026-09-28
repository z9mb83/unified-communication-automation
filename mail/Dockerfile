FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY brands/ brands/
COPY brands_master/ brands_master/
COPY main.py daily_maintenance.py daily_report.py report_core.py ./

ENV PYTHONUNBUFFERED=1
ENV RUNTIME_ENV=cloud_run
ENV STATE_BACKEND=firestore

# Default task is the sender; the maintenance job overrides this at
# `gcloud run jobs deploy` / `gcloud run jobs execute` with --command/--args.
ENTRYPOINT ["python", "main.py"]
