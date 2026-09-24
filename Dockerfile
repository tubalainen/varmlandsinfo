FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Stockholm \
    DATA_DIR=/data \
    PUID=1000 \
    PGID=1000

WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Hämtad data sparas här och monteras från värden (se docker-compose.yaml)
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4)"

# Entrypointen startar som root bara för att ge /data rätt ägare och byter sedan till PUID:PGID
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
