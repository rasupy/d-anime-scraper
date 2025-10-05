FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

ARG BUILD_REV=1
ENV BUILD_REV=${BUILD_REV}
COPY app ./app

# Create non-root user (align with typical host UID=1000; override via build args if needed)
# docker-compose.yml から APP_UID/APP_GID を渡し .env の HOST_UID/HOST_GID で可変化
ARG APP_USER=appuser
ARG APP_UID=1000
ARG APP_GID=1000
RUN groupadd -g ${APP_GID} ${APP_USER} && \
    useradd -m -u ${APP_UID} -g ${APP_GID} ${APP_USER} && \
    chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_USER}

# 実行時に OUT ディレクトリを作成してスクレイピング
CMD ["python", "app/scraper.py"]
