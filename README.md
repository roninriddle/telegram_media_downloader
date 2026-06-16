# Telegram Media Downloader Web Edition

Version: `0.0.2`

This is a Docker-first web edition of Telegram Media Downloader. On first launch, the home page is the configuration editor. You can fill `api_id`, `api_hash`, `bot_token`, chats, media types, save paths, proxy, upload drive, web password, and the rest of the config from the browser. The page also includes a full YAML editor, so every value in `config.yaml` remains visible and editable.

Telegram login is handled in the web UI as well. You no longer need to SSH into the container to enter the phone number, verification code, or two-step verification password.

## Quick Start

```sh
git clone https://github.com/roninriddle/telegram_media_downloader.git
cd telegram_media_downloader
docker compose up -d
```

The compose file pulls:

```text
roninriddle/telegram_media_downloader:0.0.2
```

Open:

```text
http://localhost:5055
```

If the config is missing or still contains placeholder values, the container starts the web UI only and will not connect to Telegram. Saving a complete config from the Config page automatically restarts the container to apply it (relies on `restart: unless-stopped` in `docker-compose.yaml`). After completing Telegram login, restart the container manually:

```sh
docker compose down
docker compose up -d
```

## Web Config Flow

1. Open the Config page.
2. Fill Telegram `api_id`, `api_hash`, and optional `bot_token`.
3. Add chats or channels in Chats.
4. Configure media types, file formats, save paths, naming rules, proxy, upload drive, web password, and other fields.
5. Use Full YAML when you need to edit any field not represented by a form control.
6. Click Save and Restart (or Save YAML and Restart).

The page reports whether the config is ready to start. If it is, the container restarts itself automatically to apply the new config; if required fields are still missing, it saves as a draft without restarting.

## Telegram Login

1. Enter the phone number with country code, for example `+8613800000000`.
2. Click Send code.
3. Enter the verification code received in Telegram.
4. If two-step verification is enabled, enter the 2FA password.
5. Click Verify.

The Telegram session is stored in `./sessions` and survives container restarts.

## Docker Persistence

`docker-compose.yaml` mounts these local directories:

```text
./config    -> /config
./downloads -> /app/downloads
./log       -> /app/log
./sessions  -> /app/sessions
./temp      -> /app/temp
```

The image stores application code in `/opt/tmd`. `/app` is only used for runtime data. Do not mount a host directory over `/opt/tmd`.

Config files:

```text
/config/config.yaml
/config/data.yaml
```

Environment variables:

```yaml
TMD_CONFIG_FILE: /config/config.yaml
TMD_DATA_FILE: /config/data.yaml
TMD_SAVE_PATH: /app/downloads
TMD_TEMP_PATH: /app/temp
TMD_LOG_PATH: /app/log
TMD_SESSION_PATH: /app/sessions
```

## Commands

```sh
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

## Acknowledgements

Thanks to the original [tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader) project and its contributors for the downloader core.
