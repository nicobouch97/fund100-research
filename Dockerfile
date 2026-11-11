# Fund-100 Railway schedule-observer prototype ONLY.
# No broker, GitHub authentication, live trading, credentials, or HTTP server.
# The rest of the repository is deliberately not copied into this image.
FROM python:3.12-slim
RUN groupadd --system observer && useradd --system --gid observer --no-create-home observer
WORKDIR /app
COPY --chown=observer:observer fund100_railway_schedule_observer_dryrun_v1_0.py /app/observer.py
USER observer
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FUND100_MODE=DRY_RUN_NO_BROKER
CMD ["python", "-u", "/app/observer.py"]
