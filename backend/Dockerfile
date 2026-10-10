FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 app
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
COPY --chown=app:app . .
# Never run as root: a compromised process can't modify the image or other containers' files.
USER app
ENV HF_HOME=/home/app/.cache/huggingface
EXPOSE 8000
# One worker (in-memory realtime state). Small WS frames; trust X-Forwarded-* only from the proxy network.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --ws-max-size 65536 --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
