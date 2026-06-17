#!/bin/sh
set -e

# 确保 /app 下的子目录存在（挂载宿主机目录后容器内镜像层被覆盖，需手动建）
mkdir -p /app/downloads /app/log /app/sessions /app/temp

cat <<EOF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Telegram Media Downloader — 挂载目录说明
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  只需映射两个目录：
  ─────────────────────────────────────────────────
  本地目录   →  容器内路径   说明
  ─────────────────────────────────────────────────
  <任意>     →  /config      配置文件目录
               config.yaml / data.yaml / task_history.json

  <任意>     →  /app         数据目录（子目录自动创建）
               downloads/   下载文件
               log/         运行日志
               sessions/    Telegram 登录会话
               temp/        下载临时文件

  Web 界面：http://localhost:${TMD_WEB_PORT:-5000}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF

# 首次部署：config.yaml 不存在时提示
if [ ! -f "${TMD_CONFIG_FILE:-/config/config.yaml}" ]; then
    echo "  [提示] 未检测到 config.yaml，请打开 Web 界面完成初始配置。"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

exec python /opt/tmd/media_downloader.py "$@"
