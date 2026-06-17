"""Configuration defaults, schema metadata, and validation helpers."""

import copy
import os
from typing import Any, Dict

CONFIG_PLACEHOLDERS = {
    "",
    "your_api_hash",
    "your_api_id",
    "your_bot_token",
    "telegram_chat_id",
    "telegram_chat_id_2",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_hash": "",
    "api_id": "",
    "bot_token": "",
    "chat": [
        {
            "chat_id": "",
            "last_read_message_id": 0,
            "download_filter": "",
            "upload_telegram_chat_id": "",
        }
    ],
    "media_types": [
        "audio",
        "document",
        "photo",
        "video",
        "voice",
        "video_note",
        "animation",
    ],
    "file_formats": {
        "audio": ["all"],
        "document": ["all"],
        "video": ["all"],
    },
    "save_path": os.environ.get(
        "TMD_SAVE_PATH", os.path.join(os.path.abspath("."), "downloads")
    ),
    "file_path_prefix": ["chat_title", "media_datetime"],
    "file_name_prefix": ["message_id", "file_name"],
    "file_name_prefix_split": " - ",
    "upload_drive": {
        "enable_upload_file": False,
        "remote_dir": "",
        "upload_adapter": "rclone",
        "rclone_path": "./rclone/rclone",
        "before_upload_file_zip": False,
        "after_upload_file_delete": False,
    },
    "hide_file_name": False,
    "max_download_task": 5,
    "max_concurrent_transmissions": 25,
    "web_host": "0.0.0.0",
    "web_port": 5000,
    "web_login_secret": "",
    "debug_web": False,
    "language": "EN",
    "log_level": "INFO",
    "start_timeout": 60,
    "forward_limit": 33,
    "after_upload_telegram_delete": True,
    "allowed_user_ids": ["me"],
    "date_format": "%Y_%m",
    "drop_no_audio_video": False,
    "enable_download_txt": False,
    "filter_advertisement_list": [],
    "replace_advertisement_list": [],
    "group_add_advertisement": {},
    "proxy": {},
}

CONFIG_SCHEMA = {
    "telegram": ["api_id", "api_hash", "bot_token", "chat"],
    "media": ["media_types", "file_formats"],
    "paths": ["save_path", "file_path_prefix", "file_name_prefix"],
    "runtime": [
        "web_host",
        "web_port",
        "language",
        "log_level",
        "max_download_task",
        "max_concurrent_transmissions",
    ],
    "upload_drive": list(DEFAULT_CONFIG["upload_drive"].keys()),
    "filters": [
        "allowed_user_ids",
        "filter_advertisement_list",
        "replace_advertisement_list",
        "group_add_advertisement",
    ],
}


def get_default_config() -> Dict[str, Any]:
    """Return a complete editable config skeleton."""
    return copy.deepcopy(DEFAULT_CONFIG)


def plain(value):
    """Convert ruamel objects into JSON/YAML friendly Python values."""
    if isinstance(value, dict):
        return {key: plain(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


def merge_config(defaults: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a partial config onto defaults while preserving unknown keys."""
    merged = copy.deepcopy(defaults)
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


def is_placeholder(value) -> bool:
    """Return whether a value is empty or a sample placeholder."""
    return str(value or "").strip() in CONFIG_PLACEHOLDERS


def get_config_errors(config: Dict[str, Any]) -> list:
    """Return human readable config errors that block downloader startup."""
    errors = []
    api_id = str(config.get("api_id", "")).strip()
    if is_placeholder(api_id):
        errors.append("api_id is required")
    elif not api_id.isdigit():
        errors.append("api_id must be numeric")

    if is_placeholder(config.get("api_hash", "")):
        errors.append("api_hash is required")

    chats = config.get("chat", [])
    if not isinstance(chats, list) or not chats:
        errors.append("at least one chat is required")
    else:
        has_chat = False
        for chat in chats:
            if isinstance(chat, dict) and not is_placeholder(chat.get("chat_id", "")):
                has_chat = True
                break
        if not has_chat:
            errors.append("at least one chat_id is required")

    media_types = config.get("media_types", [])
    if not isinstance(media_types, list) or not media_types:
        errors.append("media_types must include at least one media type")

    file_formats = config.get("file_formats", {})
    if not isinstance(file_formats, dict):
        errors.append("file_formats must be a YAML object")

    return errors


def is_config_ready(config: Dict[str, Any]) -> bool:
    """Return whether config is complete enough to start the downloader."""
    return not get_config_errors(config)
