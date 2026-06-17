#!/bin/sh
set -e

cat <<EOF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Telegram Media Downloader — 挂载目录说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  本地目录              →  容器内路径
  ─────────────────────────────────────────────────
  ./config              →  /config
    config.yaml         配置文件
    data.yaml           下载进度记录
    task_history.json   任务历史

  ./downloads           →  /app/downloads   下载文件存放目录
  ./log                 →  /app/log         运行日志
  ./sessions            →  /app/sessions    Telegram 登录会话
  ./temp                →  /app/temp        下载临时文件

  Web 界面：http://localhost:$(echo "${TMD_WEB_PORT:-5000}")
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

# 首次部署：config.yaml 不存在时提示
if [ ! -f "${TMD_CONFIG_FILE:-/config/config.yaml}" ]; then
    echo "  [提示] 未检测到 config.yaml，请打开 Web 界面完成初始配置。"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

exec python /opt/tmd/media_downloader.py "$@"
