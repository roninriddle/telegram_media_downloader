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

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    TMD_CONFIG_FILE=/config/config.yaml \
    TMD_DATA_FILE=/config/data.yaml \
    TMD_SAVE_PATH=/app/downloads

# Copy installed deps from build stage
COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy rclone to the path expected by the app (matches code default: ./rclone/rclone)
RUN mkdir -p /config /app/rclone /app/downloads /app/log /app/sessions /app/temp
COPY --from=build /usr/bin/rclone /app/rclone/rclone

# Copy app source code
COPY . /app

EXPOSE 5000

CMD ["python", "media_downloader.py"]
