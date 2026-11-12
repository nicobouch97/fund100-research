# Fund-100 Railway public schedule diagnostic + inert OAuth callback preflight.
# NO live broker account, OAuth code exchange, private keys, order authority,
# GitHub write token or production heartbeat. Only two Python modules copied.
FROM python:3.12-slim
RUN groupadd --system observer && useradd --system --gid observer --no-create-home observer
WORKDIR /app
COPY --chown=observer:observer fund100_railway_schedule_observer_dryrun_v1_0.py /app/fund100_railway_schedule_observer_dryrun_v1_0.py
COPY --chown=observer:observer fund100_railway_risk_watch_http_preflight_v1_0.py /app/fund100_railway_risk_watch_http_preflight_v1_0.py
USER observer
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FUND100_MODE=DRY_RUN_NO_BROKER
EXPOSE 8080
CMD ["python", "-u", "/app/fund100_railway_risk_watch_http_preflight_v1_0.py"]
