"""web ui for media download"""

import asyncio
import logging
import os
import shutil
import threading
import time
from io import StringIO
from typing import Any, Dict, Optional, Tuple

from flask import Flask, jsonify, render_template, request
from flask_login import LoginManager, UserMixin, login_required, login_user
import pyrogram
from ruamel import yaml

import utils
from module import task_history
from module.app import Application
from module.config_schema import (
    CONFIG_SCHEMA,
    get_config_errors,
    get_default_config,
    is_placeholder,
    merge_config,
    plain,
)
from module.download_stat import (
    DownloadState,
    get_download_result,
    get_download_state,
    get_total_download_speed,
    set_download_state,
)
from utils.crypto import AesBase64
from utils.format import format_byte

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

_yaml = yaml.YAML()
_yaml.default_flow_style = False
_flask_app = Flask(__name__)

_flask_app.secret_key = "tdl"
_login_manager = LoginManager()
_login_manager.login_view = "login"
_login_manager.init_app(_flask_app)
web_login_users: dict = {}
deAesCrypt = AesBase64("1234123412ABCDEF", "ABCDEF1234123412")
_application: Optional[Application] = None
_auth_loop: Optional[asyncio.AbstractEventLoop] = None
_auth_thread: Optional[threading.Thread] = None
_auth_clients: Dict[str, Dict[str, Any]] = {}
AUTH_CLIENT_TTL = 600


def _config_path(app: Application) -> str:
    """Return the absolute path to the active config file."""
    if os.path.isabs(app.config_file):
        return app.config_file
    return os.path.join(os.path.abspath("."), app.config_file)


def _read_config(app: Application) -> Tuple[Dict[str, Any], bool, str]:
    """Read config.yaml or return defaults when it is missing/unreadable."""
    path = _config_path(app)
    defaults = get_default_config()
    if not os.path.isfile(path):
        return defaults, False, ""

    try:
        with open(path, encoding="utf-8") as config_file:
            loaded = _yaml.load(config_file.read()) or {}
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return defaults, True, str(exc)

    if not isinstance(loaded, dict):
        return defaults, True, "config.yaml must contain a YAML object"

    return merge_config(defaults, plain(loaded)), True, ""


def _dump_config(config: Dict[str, Any]) -> str:
    """Dump config to YAML text."""
    output = StringIO()
    _yaml.dump(config, output)
    return output.getvalue()


def _write_config(app: Application, config: Dict[str, Any]):
    """Persist config.yaml."""
    path = _config_path(app)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as config_file:
        _yaml.dump(config, config_file)


def _schedule_restart(delay: float = 1.0):
    """Exit the process so Docker's `restart: unless-stopped` policy reloads the new config."""

    def _exit():
        time.sleep(delay)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()


def _path_status(label: str, path: str, expect_file: bool = False) -> Dict[str, Any]:
    """Return existence, writability, and free-space details for a path."""
    absolute_path = os.path.abspath(path)
    check_path = os.path.dirname(absolute_path) if expect_file else absolute_path
    exists = os.path.exists(absolute_path)
    target_exists = os.path.exists(check_path)
    writable = os.access(check_path, os.W_OK) if target_exists else False
    free_bytes = None
    try:
        usage = shutil.disk_usage(check_path if target_exists else os.path.dirname(check_path))
        free_bytes = usage.free
    except OSError:
        pass
    return {
        "label": label,
        "path": absolute_path,
        "exists": exists,
        "writable": writable,
        "free": format_byte(free_bytes or 0),
    }


def _log_file_path(app: Application) -> str:
    """Return the active file log path."""
    return os.path.join(app.log_file_path, "tdl.log")


def _tail_lines(path: str, lines: int = 200) -> str:
    """Return the last N lines of a UTF-8 text file."""
    if not os.path.isfile(path):
        return ""
    lines = max(1, min(lines, 2000))
    with open(path, "rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        end = log_file.tell()
        block_size = 4096
        data = b""
        while end > 0 and data.count(b"\n") <= lines:
            read_size = min(block_size, end)
            end -= read_size
            log_file.seek(end)
            data = log_file.read(read_size) + data
    return b"\n".join(data.splitlines()[-lines:]).decode("utf-8", errors="replace")


def _get_application() -> Application:
    """Return the application bound to the web server."""
    if _application is None:
        raise RuntimeError("web application is not initialized")
    return _application


def _auth_key() -> str:
    """Return the single-user auth session key."""
    return "root"


def _ensure_auth_loop() -> asyncio.AbstractEventLoop:
    """Start a dedicated event loop for Telegram login requests."""
    global _auth_loop
    global _auth_thread
    if _auth_loop and _auth_loop.is_running():
        return _auth_loop

    _auth_loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(_auth_loop)
        _auth_loop.run_forever()

    _auth_thread = threading.Thread(target=run_loop, daemon=True)
    _auth_thread.start()
    return _auth_loop


def _run_auth(coro):
    """Run a Telegram login coroutine on the auth loop."""
    loop = _ensure_auth_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)


async def _close_auth_client(key: str):
    """Close a pending Telegram login client."""
    auth = _auth_clients.pop(key, None)
    if not auth:
        return
    client = auth.get("client")
    if client and getattr(client, "is_connected", False):
        await client.disconnect()


async def _cleanup_auth_clients():
    """Disconnect stale pending Telegram login clients."""
    now = time.time()
    for key, auth in list(_auth_clients.items()):
        if now - auth.get("created_at", now) > AUTH_CLIENT_TTL:
            await _close_auth_client(key)


def _session_file_path(app: Application) -> str:
    """Return the expected Pyrogram session file path."""
    return os.path.join(app.session_file_path, "media_downloader.session")


async def _send_telegram_code(
    app: Application, phone_number: str, api_id: str, api_hash: str, proxy: dict
):
    """Send Telegram login code and keep the client connected for verification."""
    from module.pyrogram_extension import HookClient

    key = _auth_key()
    await _cleanup_auth_clients()
    await _close_auth_client(key)
    os.makedirs(app.session_file_path, exist_ok=True)
    client = HookClient(
        "media_downloader",
        api_id=int(api_id),
        api_hash=api_hash,
        proxy=proxy,
        workdir=app.session_file_path,
        start_timeout=app.start_timeout,
        no_updates=True,
    )
    await client.connect()
    sent_code = await client.send_code(phone_number)
    _auth_clients[key] = {
        "client": client,
        "phone_number": phone_number,
        "phone_code_hash": sent_code.phone_code_hash,
        "created_at": time.time(),
    }
    return {"success": True, "expires_in": 300}


async def _verify_telegram_code(phone_code: str, password: str = ""):
    """Verify Telegram login code and optional 2FA password."""
    key = _auth_key()
    await _cleanup_auth_clients()
    auth = _auth_clients.get(key)
    if not auth:
        return {
            "success": False,
            "password_required": False,
            "errors": ["please send a verification code first"],
        }

    client = auth["client"]
    try:
        if auth.get("password_required"):
            if not password:
                return {
                    "success": False,
                    "password_required": True,
                    "errors": ["two-step verification password is required"],
                }
            await client.check_password(password)
        else:
            try:
                await client.sign_in(
                    auth["phone_number"],
                    auth["phone_code_hash"],
                    phone_code,
                )
            except pyrogram.errors.SessionPasswordNeeded:
                auth["password_required"] = True
                if not password:
                    return {
                        "success": False,
                        "password_required": True,
                        "errors": ["two-step verification password is required"],
                    }
                await client.check_password(password)

        me = await client.get_me()
        await _close_auth_client(key)
        return {
            "success": True,
            "password_required": False,
            "user": {
                "id": getattr(me, "id", ""),
                "username": getattr(me, "username", ""),
                "first_name": getattr(me, "first_name", ""),
            },
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return {
            "success": False,
            "password_required": False,
            "errors": [str(exc)],
        }


class User(UserMixin):
    """Web Login User"""

    def __init__(self):
        self.sid = "root"

    @property
    def id(self):
        """ID"""
        return self.sid


@_login_manager.user_loader
def load_user(_):
    """
    Load a user object from the user ID.

    Returns:
        User: The user object.
    """
    return User()


def get_flask_app() -> Flask:
    """get flask app instance"""
    return _flask_app


def _format_download_record(chat_id, idx, value: Dict[str, Any]) -> Dict[str, str]:
    """Format a download record for layui tables."""
    total_size = value.get("total_size", 0) or 0
    down_byte = value.get("down_byte", 0) or 0
    download_progress = 0
    if total_size > 0:
        download_progress = round(down_byte / total_size * 100, 1)
    file_name = value.get("file_name", "")
    return {
        "chat": f"{chat_id}",
        "id": f"{idx}",
        "filename": os.path.basename(file_name),
        "total_size": f"{format_byte(total_size)}",
        "download_progress": f"{download_progress}",
        "download_speed": format_byte(value.get("download_speed", 0) or 0) + "/s",
        "save_path": file_name.replace("\\", "/"),
        "status": value.get("status", ""),
    }


def run_web_server(app: Application):
    """
    Runs a web server using the Flask framework.
    """

    get_flask_app().run(
        app.web_host, app.web_port, debug=app.debug_web, use_reloader=False
    )


# pylint: disable = W0603
def init_web(app: Application):
    """
    Set the value of the users variable.

    Args:
        users: The list of users to set.

    Returns:
        None.
    """
    global web_login_users
    global _application
    _application = app
    if app.web_login_secret:
        web_login_users = {"root": app.web_login_secret}
        _flask_app.config["LOGIN_DISABLED"] = False
    else:
        _flask_app.config["LOGIN_DISABLED"] = True
    if app.debug_web:
        threading.Thread(target=run_web_server, args=(app,)).start()
    else:
        threading.Thread(
            target=get_flask_app().run, daemon=True, args=(app.web_host, app.web_port)
        ).start()


@_flask_app.route("/login", methods=["GET", "POST"])
def login():
    """
    Function to handle the login route.

    Parameters:
    - No parameters

    Returns:
    - If the request method is "POST" and the username and
      password match the ones in the web_login_users dictionary,
      it returns a JSON response with a code of "1".
    - Otherwise, it returns a JSON response with a code of "0".
    - If the request method is not "POST", it returns the rendered "login.html" template.
    """
    if request.method == "POST":
        username = "root"
        web_login_form = {}
        for key, value in request.form.items():
            if value:
                value = deAesCrypt.decrypt(value)
            web_login_form[key] = value

        if not web_login_form.get("password"):
            return jsonify({"code": "0"})

        password = web_login_form["password"]
        if username in web_login_users and web_login_users[username] == password:
            user = User()
            login_user(user)
            return jsonify({"code": "1"})

        return jsonify({"code": "0"})

    return render_template("login.html")


@_flask_app.route("/")
@login_required
def index():
    """Index html"""
    current_app = _get_application()
    config, config_exists, config_error = _read_config(current_app)
    config_errors = get_config_errors(config)
    if config_error:
        config_errors.insert(0, config_error)
    return render_template(
        "index.html",
        download_state=(
            "pause" if get_download_state() is DownloadState.Downloading else "continue"
        ),
        config_exists=config_exists,
        config_ready=not config_errors,
        config_errors=config_errors,
        config_path=_config_path(current_app),
    )


@_flask_app.route("/get_download_status")
@login_required
def get_download_speed():
    """Get download speed"""
    return jsonify(
        {
            "download_speed": format_byte(get_total_download_speed()) + "/s",
            "upload_speed": "0.00 B/s",
        }
    )


@_flask_app.route("/set_download_state", methods=["POST"])
@login_required
def web_set_download_state():
    """Set download state"""
    state = request.args.get("state")

    if state == "continue" and get_download_state() is DownloadState.StopDownload:
        set_download_state(DownloadState.Downloading)
        return "pause"

    if state == "pause" and get_download_state() is DownloadState.Downloading:
        set_download_state(DownloadState.StopDownload)
        return "continue"

    return state


@_flask_app.route("/get_app_version")
def get_app_version():
    """Get telegram_media_downloader version"""
    return utils.__version__


@_flask_app.route("/healthz")
def healthz():
    """Container health check endpoint."""
    return jsonify({"ok": True, "version": utils.__version__})


@_flask_app.route("/api/system/status")
@login_required
def web_system_status():
    """Return runtime and mounted path status."""
    current_app = _get_application()
    paths = [
        _path_status("config", _config_path(current_app), expect_file=True),
        _path_status("data", current_app.app_data_file, expect_file=True),
        _path_status("downloads", current_app.save_path),
        _path_status("temp", current_app.temp_save_path),
        _path_status("log", current_app.log_file_path),
        _path_status("sessions", current_app.session_file_path),
        _path_status("task_history", task_history.HISTORY_FILE, expect_file=True),
    ]
    return jsonify(
        {
            "version": utils.__version__,
            "web_host": current_app.web_host,
            "web_port": current_app.web_port,
            "code_path": os.path.abspath(os.getcwd()),
            "paths": paths,
        }
    )


@_flask_app.route("/api/logs")
@login_required
def web_logs():
    """Return the tail of the file log."""
    current_app = _get_application()
    lines = request.args.get("lines", "200")
    try:
        line_count = int(lines)
    except ValueError:
        line_count = 200
    path = _log_file_path(current_app)
    return jsonify({"path": path, "content": _tail_lines(path, line_count)})


@_flask_app.route("/get_download_list")
@login_required
def get_download_list():
    """get download list"""
    if request.args.get("already_down") is None:
        return jsonify([])

    already_down = request.args.get("already_down") == "true"

    download_result = get_download_result()
    result = []
    for chat_id, messages in download_result.items():
        for idx, value in messages.items():
            total_size = value.get("total_size", 0) or 0
            down_byte = value.get("down_byte", 0) or 0
            is_already_down = total_size > 0 and down_byte >= total_size

            if already_down and not is_already_down:
                continue

            result.append(_format_download_record(chat_id, idx, value))

    if already_down:
        seen = {(item["chat"], item["id"]) for item in result}
        for item in task_history.list_history(status="done"):
            key = (item.get("chat", ""), item.get("id", ""))
            if key not in seen:
                result.append(_format_download_record(key[0], key[1], item))

    return jsonify(result)


@_flask_app.route("/api/tasks/history")
@login_required
def web_task_history():
    """Return persisted task history."""
    status = request.args.get("status", "")
    rows = [
        _format_download_record(item.get("chat", ""), item.get("id", ""), item)
        for item in task_history.list_history(status=status)
    ]
    return jsonify({"history_file": task_history.HISTORY_FILE, "items": rows})


@_flask_app.route("/api/config", methods=["GET"])
@login_required
def web_get_config():
    """Return editable config data."""
    current_app = _get_application()
    config, config_exists, config_error = _read_config(current_app)
    errors = get_config_errors(config)
    if config_error:
        errors.insert(0, config_error)
    return jsonify(
        {
            "config": config,
            "yaml": _dump_config(config),
            "exists": config_exists,
            "ready": not errors,
            "errors": errors,
            "path": _config_path(current_app),
        }
    )


@_flask_app.route("/api/config/schema")
@login_required
def web_config_schema():
    """Return config schema metadata and defaults."""
    return jsonify({"schema": CONFIG_SCHEMA, "defaults": get_default_config()})


@_flask_app.route("/api/config", methods=["POST"])
@login_required
def web_save_config():
    """Save edited config data and restart the container to apply it."""
    current_app = _get_application()
    payload = request.get_json(silent=True) or {}
    config = None
    if "yaml" in payload:
        try:
            config = _yaml.load(payload.get("yaml") or "") or {}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            return jsonify({"success": False, "errors": [str(exc)]}), 400
    else:
        config = payload.get("config", {})

    if not isinstance(config, dict):
        return (
            jsonify({"success": False, "errors": ["config must be a YAML object"]}),
            400,
        )

    config = merge_config(get_default_config(), plain(config))
    _write_config(current_app, config)
    current_app.config = config
    errors = get_config_errors(config)
    # Only restart once the config is actually usable, otherwise we'd just
    # bounce the container into the same incomplete state forever.
    restarting = not errors
    if restarting:
        _schedule_restart()
    return jsonify(
        {
            "success": True,
            "ready": not errors,
            "errors": errors,
            "restart_required": True,
            "restarting": restarting,
            "path": _config_path(current_app),
            "yaml": _dump_config(config),
        }
    )


@_flask_app.route("/api/auth/status")
@login_required
def web_auth_status():
    """Return Telegram session status."""
    current_app = _get_application()
    key = _auth_key()
    auth = _auth_clients.get(key)
    pending = bool(auth and time.time() - auth.get("created_at", 0) <= AUTH_CLIENT_TTL)
    return jsonify(
        {
            "session_exists": os.path.exists(_session_file_path(current_app)),
            "session_path": _session_file_path(current_app),
            "pending": pending,
        }
    )


@_flask_app.route("/api/auth/send_code", methods=["POST"])
@login_required
def web_auth_send_code():
    """Send Telegram login verification code."""
    current_app = _get_application()
    payload = request.get_json(silent=True) or {}
    phone_number = str(payload.get("phone_number", "")).strip()
    api_id = str(payload.get("api_id") or current_app.config.get("api_id", "")).strip()
    api_hash = str(
        payload.get("api_hash") or current_app.config.get("api_hash", "")
    ).strip()

    if not phone_number:
        return jsonify({"success": False, "errors": ["phone_number is required"]}), 400
    if is_placeholder(api_id) or not api_id.isdigit():
        return jsonify({"success": False, "errors": ["valid api_id is required"]}), 400
    if is_placeholder(api_hash):
        return jsonify({"success": False, "errors": ["api_hash is required"]}), 400
    proxy = payload.get("proxy")
    if not isinstance(proxy, dict):
        proxy = current_app.config.get("proxy") or current_app.proxy

    try:
        result = _run_auth(
            _send_telegram_code(current_app, phone_number, api_id, api_hash, proxy)
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return jsonify({"success": False, "errors": [str(exc)]}), 500
    return jsonify(result)


@_flask_app.route("/api/auth/verify", methods=["POST"])
@login_required
def web_auth_verify():
    """Verify Telegram login code."""
    payload = request.get_json(silent=True) or {}
    phone_code = str(payload.get("phone_code", "")).strip().replace(" ", "")
    password = str(payload.get("password", ""))
    if not phone_code:
        return jsonify({"success": False, "errors": ["phone_code is required"]}), 400

    try:
        result = _run_auth(_verify_telegram_code(phone_code, password))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return jsonify({"success": False, "errors": [str(exc)]}), 500

    status_code = 200 if result.get("success") or result.get("password_required") else 400
    return jsonify(result), status_code
