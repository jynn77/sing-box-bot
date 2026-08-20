import os, re, json, time, uuid, base64, platform, subprocess, threading, requests, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv()

# ── 日志级别 ──────────────────────────────────────────
# LOG_LEVEL=0 仅节点链接+错误, 1=信息, 2=调试
LOG_LEVEL = int(os.environ.get('LOG_LEVEL') or '0')
def log(msg, level=1):
    if LOG_LEVEL >= level: print(msg, flush=True)

def error(*args):
    print('[ERROR]', *args, file=sys.stderr, flush=True)

# ── 环境变量 ──────────────────────────────────────────
UPLOAD_URL = os.environ.get('UPLOAD_URL') or ''
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
uuid_file = os.path.join(FILE_PATH, 'uuid.txt')
UUID = os.environ.get('UUID') or (
    open(uuid_file).read().strip() if os.path.exists(uuid_file) else None
) or str(uuid.uuid4())
NODE_PORT_STR = os.environ.get('NODE_PORT')
if not NODE_PORT_STR:
    error('NODE_PORT environment variable is required')
    sys.exit(1)
NODE_PORT = int(NODE_PORT_STR)
PORT = int(os.environ.get('PORT') or '3000')
LISTEN_ADDR = os.environ.get('LISTEN_ADDR') or '127.0.0.1'
SB_LOG = (os.environ.get('SB_LOG') or 'false').lower() == 'true'
NAME = os.environ.get('NAME') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
DAILY_RESTART = (os.environ.get('DAILY_RESTART') or 'false').lower() == 'true'
KOMARI_ENABLED = (os.environ.get('KOMARI_ENABLED') or 'true').lower() != 'false'
KOMARI_SERVER = os.environ.get('KOMARI_SERVER') or ''
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN') or ''

# ── 路径 ──────────────────────────────────────────────
web_path = os.path.join(FILE_PATH, 'web')
komari_path = os.path.join(FILE_PATH, 'komori')
komari_log = os.path.join(FILE_PATH, 'komori.log')
config_path = os.path.join(FILE_PATH, 'config.json')
keypair_path = os.path.join(FILE_PATH, 'keypair.txt')

# ── HTTP 处理器 ──────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f'<h2>sing-box-bot running</h2><p>hy2 + reality port: {NODE_PORT}</p>'.encode())
    def log_message(self, *a): pass

# ── 工具函数 ──────────────────────────────────────────
def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return r.stdout + r.stderr
    except Exception as e:
        error(f'Command execution failed: {cmd}\n{e}')
        return str(e)

def run_check(cmd):
    """执行命令，失败时返回 False 并打印错误"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            error(f'Command failed (code {r.returncode}): {cmd}\n{r.stderr}')
            return False
        return True
    except Exception as e:
        error(f'Command error: {cmd}\n{e}')
        return False

def get_arch():
    a = platform.machine().lower()
    return 'arm' if ('arm' in a or 'aarch64' in a) else 'amd'

def dl(name, url, retries=3):
    """下载文件，支持重试"""
    fp = os.path.join(FILE_PATH, name)
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, stream=True, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
            r.raise_for_status()
            with open(fp, 'wb') as f:
                for c in r.iter_content(8192):
                    f.write(c)
            os.chmod(fp, 0o775)
            log(f'[DOWNLOAD] {name} downloaded successfully', 2)
            return True
        except Exception as e:
            error(f'Download {name} attempt {attempt}/{retries} failed: {e}')
            try:
                os.remove(fp)
            except:
                pass
            if attempt < retries:
                time.sleep(5)
    return False

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App running', flush=True)   # 立即标记运行，让面板识别
    print('App starting...', flush=True)   # 启动标记

    log(f'=== sing-box-bot === Port: {NODE_PORT} (hy2 + reality)', 2)
    if not os.path.exists(FILE_PATH):
        os.makedirs(FILE_PATH)
    if not os.path.exists(uuid_file):
        with open(uuid_file, 'w') as f:
            f.write(UUID)
        log('[UUID] Generated and saved', 2)
    else:
        log('[UUID] Loaded from file', 2)

    if DAILY_RESTART:
        threading.Timer(86400, lambda: os._exit(0)).start()
        log('[DAILY] Restart scheduled in 24h', 2)

    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm' else 'https://amd64.ssss.nyc.mn'
    if not dl('web', f'{base}/sb'):
        error('Failed to download sing-box binary after retries')
        return

    # 加载或生成 reality keypair
    pk = puk = None
    if os.path.exists(keypair_path):
        with open(keypair_path) as f:
            parts = f.read().strip().split('\n')[:2]
        if len(parts) >= 2:
            pk, puk = parts[0], parts[1]
            log('[KEY] Loaded existing keypair', 2)
        else:
            os.remove(keypair_path)
            error('[KEY] Invalid keypair file, regenerating')
            pk = puk = None
    if not pk or not puk:
        kp = run(f'{web_path} generate reality-keypair')
        pm = re.search(r'PrivateKey:\s*(.*)', kp)
        pum = re.search(r'PublicKey:\s*(.*)', kp)
        if not (pm and pum):
            error('Failed to generate reality keypair, output:', kp)
            return
        pk, puk = pm.group(1).strip(), pum.group(1).strip()
        with open(keypair_path, 'w') as f:
            f.write(f'{pk}\n{puk}\n')
        log('[KEY] Generated and saved', 2)
    log(f'Private Key: {pk}\nPublic Key: {puk}', 3)

    # 生成证书（检查 openssl 是否成功）
    if not run_check(f'openssl ecparam -genkey -name prime256v1 -out "{FILE_PATH}/private.key"'):
        error('openssl ecparam failed')
        return
    if not run_check(f'openssl req -new -x509 -days 3650 -key "{FILE_PATH}/private.key" -out "{FILE_PATH}/cert.pem" -subj "/CN=bing.com"'):
        error('openssl req failed')
        return

    # 写入配置
    config = {
        "log": {"disabled": not SB_LOG, "level": "info", "timestamp": True} if SB_LOG else {"disabled": True},
        "inbounds": [
            {"tag": "hysteria-in", "type": "hysteria2", "listen": "::", "listen_port": NODE_PORT,
             "users": [{"password": UUID}], "masquerade": "https://bing.com",
             "tls": {"enabled": True, "alpn": ["h3"],
                      "certificate_path": f"{FILE_PATH}/cert.pem", "key_path": f"{FILE_PATH}/private.key"}},
            {"tag": "vless-reality-in", "type": "vless", "listen": "::", "listen_port": NODE_PORT,
             "users": [{"uuid": UUID, "flow": "xtls-rprx-vision"}],
             "tls": {"enabled": True, "server_name": "www.iij.ad.jp",
                      "reality": {"enabled": True, "handshake": {"server": "www.iij.ad.jp", "server_port": 443},
                                   "private_key": pk, "short_id": [""]}}}],
        "outbounds": [{"type": "direct", "tag": "direct"}]}
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    log('[CONFIG] Generated', 2)

    # 启动 sing-box（后台运行）
    log_file = f'{FILE_PATH}/sb.log' if SB_LOG else '/dev/null'
    run(f'nohup {web_path} run -c {config_path} >{log_file} 2>&1 &')
    log('[SB] sing-box launched', 2)

    # HTTP 服务（提前启动，让面板检测到端口）
    s = HTTPServer(('0.0.0.0', PORT), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    log(f'[HTTP] Listening on :{PORT}', 2)
    time.sleep(3)

    # 启动 komari（若启用）
    if KOMARI_ENABLED:
        log('[KOMARI] Starting in 5s...', 2)
        time.sleep(5)
        run_komari()
        threading.Thread(target=komari_watchdog, daemon=True).start()
        log('[KOMARI] Watchdog started (check every 5min)', 2)

    # 获取 IP 和 ISP
    try:
        ip = requests.get('http://ipv4.ip.sb', timeout=5).text.strip()
    except:
        ip = '127.0.0.1'
    try:
        isp = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except:
        try:
            isp = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        except:
            isp = {}
    isp_str = f"{isp.get('country_code') or isp.get('countryCode', '')}-{isp.get('isp') or isp.get('org', 'Unknown')}".replace(' ', '_')

    nn = f'{NAME}-{isp_str}' if NAME and NAME.strip() else isp_str
    txt = (f'hysteria2://{UUID}@{ip}:{NODE_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#{nn}'
           f'\nvless://{UUID}@{ip}:{NODE_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality'
           f'&sni=www.iij.ad.jp&fp=chrome&pbk={puk}&type=tcp&headerType=none#{nn}')
    log(f'\n{txt}\n[INFO] Port: {NODE_PORT}', 1)

    # 推送通知
    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': f'✅ 节点已就绪 | {nn}\n🌍 IP: {ip}\n\n<pre>{base64.b64encode(txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
            log('[TG] Sent', 2)
        except Exception as e:
            error(f'[TG] Failed: {e}')
    if UPLOAD_URL:
        try:
            requests.post(f'{UPLOAD_URL}/api/add-nodes', json={"nodes": [l for l in txt.split("\n") if l.strip()]},
                          headers={"Content-Type": "application/json"}, timeout=15)
            log('[UPLOAD] Nodes uploaded', 2)
        except Exception as e:
            error(f'[UPLOAD] Failed: {e}')

    # 90 秒后清理临时文件并输出运行完成标记
    def cleanup_and_announce():
        for f in [config_path, web_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception as e:
                    error(f'Cleanup remove {f} failed: {e}')
        print('\033c', end='')        # 清屏
        log('[CLEANUP] Temporary files removed, app is fully running', 3)

    threading.Timer(90, cleanup_and_announce).start()

    # 主线程保持存活
    while True:
        time.sleep(3600)

# ── komari-agent ──────────────────────────────────────
def run_komari():
    a = platform.machine().lower()
    arch_map = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    ka = next((v for k, v in arch_map.items() if k in a), None)
    if not ka and a.startswith('arm'):
        ka = 'arm'
    if not ka:
        error('[KOMARI] Unsupported arch for komari-agent')
        return

    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    if not dl('komori', url):
        error('[KOMARI] Download failed')
        return

    run(f'nohup {komari_path} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{komari_log} 2>&1 &')
    time.sleep(2)
    if os.path.exists(komari_log) and os.path.getsize(komari_log) > 0:
        lines = open(komari_log).read().strip().split('\n')[-3:]
        log(f'[KOMARI] Started, log: {komari_log}', 3)
        for l in lines:
            log(f'  {l}', 3)
    else:
        log(f'[KOMARI] No log yet: {komari_log}', 3)

def komari_alive():
    try:
        subprocess.run(['pgrep', '-f', 'komori'], capture_output=True, check=True, timeout=5)
        return True
    except:
        pass
    try:
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        return 'komori' in r.stdout
    except:
        return True

def komari_watchdog():
    if KOMARI_ENABLED and not komari_alive():
        log('[KOMARI] Process not found, restarting...', 2)
        run_komari()
    threading.Timer(300, komari_watchdog).start()

if __name__ == '__main__':
    main()