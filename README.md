# sing-box-bot

基于 sing-box 的轻量节点生成器。从原 Sing-box-test 项目精简而来：

**移除**：nezha、argo、vmess、tuic、socks5、anytls、YouTube 检测、自动保活

**仅保留**：Hysteria2 + VLESS-Reality，共用端口 10280

## 快速开始

```bash
cd sing-box-bot
npm install
cp .env.example .env
# 编辑 .env，至少填入 BOT_TOKEN 和 CHAT_ID
npm start
```

## 做了什么

| 步骤 | 说明 |
|------|------|
| 下载 | 自动下载对应架构（amd64/arm64）的 sing-box 和 cloudflared |
| 证书 | 生成自签 TLS 证书（hy2 需要） |
| 密钥 | 生成 reality keypair |
| 配置 | 生成 sing-box 配置，hy2 + reality 同端口 10280 |
| 运行 | 启动 sing-box |
| 订阅 | 生成 base64 订阅，提供 HTTP 订阅链接 |
| 推送 | 推送到 Telegram 群组 |
| 清理 | 90 秒后删除二进制和敏感文件 |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `BOT_TOKEN` | — | Telegram Bot Token（填了才推 TG） |
| `CHAT_ID` | — | Telegram 群组/用户 ID |
| `NODE_PORT` | `10280` | hy2 + reality 共用端口 |
| `PORT` | `3000` | HTTP 订阅端口 |
| `SUB_PATH` | `sub` | 订阅路径 |
| `UUID` | 自动生成 | 节点 UUID |
| `NAME` | 自动检测 | 节点名称标识 |
| `UPLOAD_URL` | — | 订阅自动上传地址 |
| `CFIP` | `saas.sin.fan` | 优选域名 |
| `CFPORT` | `443` | 优选端口 |
| `FILE_PATH` | `.npm` | 运行目录 |
| `DOWNLOAD_BASE` | `https://amd64.ssss.nyc.mn` | 下载地址前缀 |
| `TG_TTL_MINUTES` | `5` | TG 消息自动删除时间（分钟） |
| `TG_CLEAN_INTERVAL` | `30` | TG 消息清理扫描间隔（秒） |

## TG 消息自动删除

Bot 推送到 Telegram 的节点消息会被自动追踪，默认 **5 分钟后自动删除**。原理：

1. `sendTG()` 发送消息后，从 API 响应中提取 `message_id` 和 `chat_id`
2. 存入内存追踪表 `Map<chatId, Map<messageId, timestamp>>`
3. 每 30 秒扫描一次，超时的消息调用 `deleteMessage` 删除
4. 删除成功/失败都从追踪表中移除，不会重复尝试

可通过 `.env` 中的 `TG_TTL_MINUTES` 调整过期时间。

## 订阅链接

运行后访问 `http://你的IP:3000/sub` 获取 base64 格式订阅。

## 目录结构

```
sing-box-bot/
├── index.js        # 主程序
├── .env            # 环境变量
├── .env.example    # 配置模板
├── package.json
└── .npm/           # 运行目录（自动创建）
    ├── config.json # sing-box 配置
    ├── sub.txt     # 订阅文件（base64）
    ├── list.txt    # 明文节点列表
    ├── key.txt     # reality 密钥
    ├── cert.pem    # TLS 证书
    └── private.key # TLS 私钥
```