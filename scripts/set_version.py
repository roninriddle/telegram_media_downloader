"""Update project version references."""

import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("usage: scripts/set_version.py VERSION")

version = sys.argv[1]
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise SystemExit("version must look like X.Y.Z")

replacements = {
    Path("utils/__init__.py"): (
        r'__version__ = "\d+\.\d+\.\d+"',
        f'__version__ = "{version}"',
    ),
    Path("README.md"): (r"Version: `\d+\.\d+\.\d+`", f"Version: `{version}`"),
    Path("README_CN.md"): (r"版本：`\d+\.\d+\.\d+`", f"版本：`{version}`"),
    Path("docker-compose.yaml"): (
        r"roninriddle/telegram_media_downloader:\d+\.\d+\.\d+",
        f"roninriddle/telegram_media_downloader:{version}",
    ),
}

for path, (pattern, replacement) in replacements.items():
    text = path.read_text(encoding="utf-8")
    updated = re.sub(pattern, replacement, text)
    path.write_text(updated, encoding="utf-8")

for readme in (Path("README.md"), Path("README_CN.md")):
    text = readme.read_text(encoding="utf-8")
    text = re.sub(
        r"roninriddle/telegram_media_downloader:\d+\.\d+\.\d+",
        f"roninriddle/telegram_media_downloader:{version}",
        text,
    )
    readme.write_text(text, encoding="utf-8")
