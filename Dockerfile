# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENIQ_DATA_DIR=/data \
    DEBUG=0 \
    HTTPS=0

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr fonts-dejavu-core libpcap0.8 postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 openiq \
    && useradd --uid 10001 --gid openiq --create-home openiq \
    && mkdir /data \
    && chown openiq:openiq /data

COPY requirements.lock ./
RUN python -m pip install --requirement requirements.lock
COPY . .
RUN SECRET_KEY=build-time-static-assets-only python manage.py collectstatic --noinput \
    && chmod +x scripts/container-entrypoint.sh

USER openiq
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).read()"
ENTRYPOINT ["/app/scripts/container-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "90", "--access-logfile", "-", "--access-logformat", "%(h)s %(m)s %(U)s %(s)s %(L)s", "--error-logfile", "-"]
