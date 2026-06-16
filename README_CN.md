# Telegram Media Downloader Web 版

版本：`0.0.1`

这是一个面向 Docker 部署的 Telegram Media Downloader Web 版。容器首次启动后会直接进入 Web 首页，首页就是配置编辑器：`api_id`、`api_hash`、`bot_token`、聊天列表、媒体类型、保存路径、代理、网盘上传、网页密码等配置都可以在页面里填写。页面也包含完整 YAML 编辑区，配置文件里的全部内容都可以查看和保存。

Telegram 登录认证也已经搬到 Web：不再需要 SSH 进入容器输入手机号和验证码。

## 快速启动

```sh
git clone https://github.com/roninriddle/telegram_media_downloader.git
cd telegram_media_downloader
docker compose up -d
```

打开：

```text
http://localhost:5055
```

首次启动时，如果配置缺失或仍是示例占位值，程序只启动 Web UI，不会连接 Telegram。完成配置和登录后重启容器即可开始下载：

```sh
docker compose down
docker compose up -d
```

## Web 配置流程

1. 进入首页 Config。
2. 填写 Telegram 的 `api_id`、`api_hash`，以及可选的 `bot_token`。
3. 在 Chats 中添加要下载的聊天或频道。
4. 按需配置媒体类型、文件格式、保存路径、命名规则、代理、网盘上传、网页登录密码等字段。
5. 如果需要编辑未出现在表单中的字段，使用 Full YAML 区域直接编辑完整配置。
6. 点击 Save 或 Save YAML。

保存后页面会提示配置是否已经满足启动要求。运行中的下载进程不会热重载核心配置，修改后请重启容器。

## Telegram 登录

1. 在 Telegram Login 区输入带国家码的手机号，例如 `+8613800000000`。
2. 点击 Send code。
3. 输入 Telegram 客户端收到的验证码。
4. 如果账号启用了两步验证，填写 2FA password。
5. 点击 Verify。

登录会话保存在 `./sessions`，容器重启后仍然有效。

## Docker 持久化目录

`docker-compose.yaml` 默认挂载：

```text
./config    -> /config
./downloads -> /app/downloads
./log       -> /app/log
./sessions  -> /app/sessions
./temp      -> /app/temp
```

配置文件位置：

```text
/config/config.yaml
/config/data.yaml
```

可用环境变量：

```yaml
TMD_CONFIG_FILE: /config/config.yaml
TMD_DATA_FILE: /config/data.yaml
TMD_SAVE_PATH: /app/downloads
```

## 常用命令

```sh
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

## 致谢

感谢原项目 [tangyoha/telegram_media_downloader](https://github.com/tangyoha/telegram_media_downloader) 及其贡献者提供的下载核心能力。
