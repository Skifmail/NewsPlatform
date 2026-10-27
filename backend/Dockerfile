FROM python:3.12-slim

WORKDIR /app

# ffmpeg + gifski: high-quality MP4→GIF for animated covers
# https://github.com/ImageOptim/gifski
ARG GIFSKI_VERSION=1.34.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl libcairo2 ffmpeg xz-utils \
    && curl -fsSL \
      "https://github.com/ImageOptim/gifski/releases/download/${GIFSKI_VERSION}/gifski-${GIFSKI_VERSION}.tar.xz" \
      -o /tmp/gifski.tar.xz \
    && tar -xJf /tmp/gifski.tar.xz -C /tmp \
    && install -m 755 /tmp/linux/gifski /usr/local/bin/gifski \
    && rm -rf /tmp/gifski.tar.xz /tmp/linux /tmp/mac /tmp/win /tmp/LICENSE /tmp/README.md \
    && rm -rf /var/lib/apt/lists/*

# PyPI mirror is configurable for servers with slow access to pypi.org.
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_DEFAULT_TIMEOUT=60 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 60 \
      --index-url "$PIP_INDEX_URL" -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
