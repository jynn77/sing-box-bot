# sing-box-bot

精简版 sing-box 节点生成器。仅 **Hysteria2 + VLESS-Reality** 双协议，无多余功能。

- ✅ 自动下载 sing-box 二进制（支持重试）
- ✅ 生成 TLS 证书 + reality keypair（持久化，重启不变）
- ✅ UUID 自动生成并持久化
- ✅ Telegram 推送订阅（点击复制）
- ✅ komari-agent 监控（可选）
- ✅ 每日重启（可选）
- ✅ 日志级别（`LOG_LEVEL=1` 看节点，`LOG_LEVEL=2` 看信息，`LOG_LEVEL=3` 看调试）
- ✅ Python 版 & Node.js 版

---

## ⚡ 快速开始

### Python 版

```bash
cd python
pip install -r requirements.txt
# 编辑 .env（至少填 NODE_PORT）
cp .env.example .env
python app.py
```

### Node.js 版

```bash
cd node
npm install
# 编辑 .env（至少填 NODE_PORT）
cp .env.example .env
node index.js
```

---

## 🔧 .env 配置说明

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `NODE_PORT` | ✅ | — | hy2 + reality 共用端口 |
| `BOT_TOKEN` | ❌ | 空 | Telegram Bot Token，填了才推送 |
| `CHAT_ID` | ❌ | 空 | Telegram 群组/用户 ID |
| `UUID` | ❌ | 自动生成 | 节点 UUID，首次运行生成并保存，后续复用 |
| `NAME` | ❌ | 自动检测 | 节点名称标识，默认使用 ISP |
| `KOMARI_ENABLED` | ❌ | `true` | komari-agent 监控开关 |
| `KOMARI_SERVER` | ❌ | 空 | komari 服务器地址 |
| `KOMARI_TOKEN` | ❌ | 空 | komari 自动发现密钥 |
| `UPLOAD_URL` | ❌ | 空 | 节点自动上传地址 |
| `FILE_PATH` | ❌ | `.cache` | 运行目录 |
| `PORT` | ❌ | `3000` | HTTP 健康页端口 |
| `DAILY_RESTART` | ❌ | `false` | 每日重启（24h 后自动退出） |
| `LOG_LEVEL` | ❌ | `0` | 日志级别：`0`=仅错误，`1`=+节点，`2`=+信息，`3`=+调试 |

### 最小配置示例

只需一行就能跑：

```env
NODE_PORT=25983
```

> Telegram 推送、komari 监控、日志都默认不填，需用时再配。

### 完整配置示例

```env
NODE_PORT=25983
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
CHAT_ID=-1001234567890
UUID=7bd180e8-1142-4387-93f5-03e8d750a896
NAME=MyServer
KOMARI_ENABLED=true
KOMARI_SERVER=https://your-komari-server.com
KOMARI_TOKEN=your-token
UPLOAD_URL=https://merge-sub.com
DAILY_RESTART=true
LOG_LEVEL=1
```

---

## 📁 目录结构

```
sing-box-bot/
├── README.md
├── python/
│   ├── app.py
│   ├── requirements.txt
│   └── .env.example
└── node/
    ├── index.js
    ├── package.json
    └── .env.example
```

## 📋 Telegram 推送格式

```
✅ 节点已就绪 | DE-Smartnet_Hosting
🌍 IP: 95.85.234.80

[base64 订阅链接 — 点击即可复制]
```

## 🛡️ komari-agent

默认开启。需在 `.env` 配置服务器地址和密钥：

```env
KOMARI_ENABLED=true
KOMARI_SERVER=https://your-server.com
KOMARI_TOKEN=your-token
```

内置 5 分钟进程保活，崩溃自动重启。

---

## 🌐 Argo 版（Cloudflare Tunnel）

基于 `cloudflared` 建立隧道，支持临时隧道（trycloudflare）和固定隧道两种模式。

### 快速开始

```bash
# Node.js 版（无需 npm install）
node node/min_argo.js

# Python 版
pip install requests python-dotenv
python python/app_argo.py
```

### Argo 版 .env 配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `UUID` | ❌ | 自动生成 | 节点 UUID |
| `NAME` | ❌ | 自动检测 | 节点名称 |
| `BOT_TOKEN` | ❌ | 空 | Telegram Bot Token |
| `CHAT_ID` | ❌ | 空 | Telegram 群组/用户 ID |
| `PORT` | ❌ | `3000` | HTTP 服务端口 |
| `SUB_PATH` | ❌ | `sub` | 订阅路径 |
| `KOMARI_SERVER` | ❌ | 空 | komari 服务器地址 |
| `KOMARI_TOKEN` | ❌ | 空 | komari 自动发现密钥 |
| `ARGO_DOMAIN` | ❌ | 空 | 固定隧道域名，留空启用临时隧道 |
| `ARGO_AUTH` | ❌ | 空 | 固定隧道 token 或 json，留空启用临时隧道 |
| `ARGO_PORT` | ❌ | `8001` | 固定隧道端口 |
| `CFIP` | ❌ | `saas.sin.fan` | 优选域名或 IP |
| `CFPORT` | ❌ | `443` | 优选端口 |
| `DISABLE_ARGO` | ❌ | `false` | 设为 `true` 禁用 argo |
| `SHOW_LOG` | ❌ | `true` | 是否显示日志 |

### 临时隧道（默认）

不设 `ARGO_DOMAIN` 和 `ARGO_TOKEN`，自动生成 `https://随机名.trycloudflare.com`。

### 固定隧道

```env
ARGO_DOMAIN=你的域名.com
ARGO_AUTH=你的token或json
```

### 完整配置示例

```env
UUID=7bd180e8-1142-4387-93f5-03e8d750a896
NAME=MyServer
ARGO_DOMAIN=your-domain.com
ARGO_AUTH=your-token
CFIP=saas.sin.fan
CFPORT=443
KOMARI_SERVER=https://your-komari-server.com
KOMARI_TOKEN=your-key
BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
CHAT_ID=-1001234567890
```

## 📝 说明

- hy2 和 reality 共用同一端口（`NODE_PORT`）
- 首次运行自动生成 UUID 和 keypair，保存在 `.cache/` 目录，重启不变
- 90 秒后自动删除二进制文件，节省磁盘
- 控制台输出节点链接，可直接复制使用
- 设 `LOG_LEVEL=1` 可看节点链接，`LOG_LEVEL=2` 看运行信息，`LOG_LEVEL=3` 看调试详情