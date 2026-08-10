# sing-box-bot

精简版 sing-box 节点生成器。支持 **Hysteria2 + VLESS-Reality 直连** 和 **Argo 隧道多协议**。

## 文件说明

| 文件 | 说明 |
|------|------|
| `python/app.py` | Python 标准版：hy2 + reality 直连 + komari |
| `python/app_max.py` | Python 全功能版：直连 + Argo 隧道 + komari |
| `node/index.js` | Node.js 标准版：hy2 + reality 直连 + komari（需 npm install） |
| `node/min.js` | Node.js 最小版：零依赖，hy2 + reality 直连 + komari |
| `python/webapp.py` | Python 纯代理版：VLESS/Trojan/SS WebSocket，零二进制依赖 + komari |
| `python/argo.py` | Python Argo 版：仅 Argo 隧道 + 多协议 WS（基于 eooce） |

---

## 快速开始

### Python 标准版

```bash
cd python
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，至少填 NODE_PORT
python app.py
```

### Python 全功能版（直连 + Argo）

```bash
cd python
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，设 NODE_PORT + ARGO 相关变量
python app_max.py
```

### Node.js 最小版（零依赖）

```bash
cd node
cp .env.example .env
node min.js
```

### Node.js 标准版

```bash
cd node
npm install
cp .env.example .env
node index.js
```

### Python 纯代理版（零二进制）

```bash
cd python
pip install aiohttp
cp .env.example .env
python webapp.py
```

---

## 环境变量

### 标准版（app.py / index.js / min.js）

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `NODE_PORT` | ✅ | — | hy2 + reality 共用端口 |
| `BOT_TOKEN` | ❌ | 空 | Telegram Bot Token |
| `CHAT_ID` | ❌ | 空 | Telegram 群组/用户 ID |
| `UUID` | ❌ | 自动生成 | 节点 UUID，持久化到文件 |
| `NAME` | ❌ | 自动检测 | 节点名称标识 |
| `KOMARI_ENABLED` | ❌ | `true` | komari 监控开关 |
| `KOMARI_SERVER` | ❌ | 空 | komari 服务器地址 |
| `KOMARI_TOKEN` | ❌ | 空 | komari 自动发现密钥 |
| `UPLOAD_URL` | ❌ | 空 | 节点自动上传地址 |
| `FILE_PATH` | ❌ | `.cache` | 运行目录 |
| `PORT` | ❌ | `3000` | HTTP 健康页端口 |
| `DAILY_RESTART` | ❌ | `false` | 每日重启（24h 后自动退出） |
| `LOG_LEVEL` | ❌ | `0` | 日志级别：`0`=仅错误，`1`=+信息，`2`=+调试 |

### 全功能版额外变量（app_max.py）

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `ARGO_DOMAIN` | ❌ | 空 | 固定隧道域名，留空启用临时隧道 |
| `ARGO_AUTH` | ❌ | 空 | 固定隧道 token 或 json |
| `ARGO_PORT` | ❌ | `8001` | 隧道端口 |
| `CFIP` | ❌ | `spring.io` | 优选域名或 IP |
| `CFPORT` | ❌ | `443` | 优选端口 |
| `PROJECT_URL` | ❌ | 空 | 项目 URL（自动保活用） |
| `AUTO_ACCESS` | ❌ | `false` | 自动保活开关 |

### Argo 版额外变量（argo.py）

参考 eooce 原始项目，支持 `ARGO_DOMAIN`、`ARGO_AUTH`、`CFIP`、`CFPORT`、`SUB_PATH`、`DISABLE_ARGO`、`SHOW_LOG` 等。

---

## 节点类型

### 直连节点（通过 `img` 二进制）

| 协议 | 传输 | 说明 |
|------|------|------|
| Hysteria2 | QUIC | 基于 UDP 的快速传输 |
| VLESS-Reality | TCP + TLS | 基于 Reality 的加密传输 |

### Argo 隧道节点（通过 `sod` 二进制 + Cloudflare Tunnel）

| 协议 | 传输 | 路径 |
|------|------|------|
| VLESS | WebSocket | `/vless-argo` |
| VMESS | WebSocket | `/vmess-argo` |
| Trojan | WebSocket | `/trojan-argo` |

---

## 日志级别

| `LOG_LEVEL` | 输出 |
|-------------|------|
| `0`（默认） | 仅错误 + App running |
| `1` | + 节点链接 + 信息日志 |
| `2` | + 调试日志 |

---

## 目录结构

```
sing-box-bot/
├── README.md
├── .gitignore
├── python/
│   ├── app.py          # 标准版（直连）
│   ├── app_max.py      # 全功能版（直连 + Argo）
│   ├── webapp.py       # 纯代理版（VLESS/Trojan/SS，零二进制）
│   ├── argo.py         # Argo 隧道版
│   ├── requirements.txt
│   └── .env.example
└── node/
    ├── index.js        # 标准版（需 npm install）
    ├── min.js          # 最小版（零依赖）
    ├── package.json
    └── .env.example
```

## 说明

- 直连节点：hy2 和 reality 共用同一端口（`NODE_PORT`）
- 首次运行自动生成 UUID 和 keypair，保存在 `.cache/` 目录，重启不变
- Argo 隧道：不设 `ARGO_AUTH` 和 `ARGO_DOMAIN` 则自动生成临时隧道（trycloudflare.com）
- 设 `LOG_LEVEL=1` 可查看节点链接