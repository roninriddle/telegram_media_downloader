FROM python:3.11.9-alpine AS build

WORKDIR /app

# Build deps for pip packages that need compilation
RUN apk add --no-cache --virtual .build-deps gcc musl-dev

# Install python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    --trusted-host pypi.python.org \
    -r requirements.txt

# Install rclone (runtime binary)
RUN apk add --no-cache rclone


FROM python:3.11.9-alpine AS runtime

WORKDIR /opt/tmd
ENV PYTHONUNBUFFERED=1 \
    TMD_CONFIG_FILE=/config/config.yaml \
    TMD_DATA_FILE=/config/data.yaml \
    TMD_SAVE_PATH=/app/downloads \
    TMD_TEMP_PATH=/app/temp \
    TMD_LOG_PATH=/app/log \
    TMD_SESSION_PATH=/app/sessions \
    TMD_TASK_HISTORY_FILE=/config/task_history.json

# Copy installed deps from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy rclone to the path expected by the app (matches code default: ./rclone/rclone)
RUN mkdir -p /config /app/downloads /app/log /app/sessions /app/temp /opt/tmd/rclone
COPY --from=build /usr/bin/rclone /opt/tmd/rclone/rclone

# Copy app source code
COPY . /opt/tmd

RUN chmod +x /opt/tmd/entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=3).read()" || exit 1

ENTRYPOINT ["/opt/tmd/entrypoint.sh"]
