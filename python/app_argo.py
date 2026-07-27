import os, re, json, time, uuid, base64, platform, subprocess, threading, requests, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv()

# ── 日志级别 ──────────────────────────────────────────
LOG_LEVEL = int(os.environ.get('LOG_LEVEL') or '0')
def log(msg, level=1):
    if LOG_LEVEL >= level: print(msg, flush=True)
def error(*args):
    print('[ERROR]', *args, file=sys.stderr, flush=True)

# ── 环境变量 ──────────────────────────────────────────
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
NAME = os.environ.get('NAME') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
ARGO_TOKEN = os.environ.get('ARGO_TOKEN') or ''

# ── 路径 ──────────────────────────────────────────────
web_path = os.path.join(FILE_PATH, 'web')
cfd_path = os.path.join(FILE_PATH, 'cfd')
cfd_log = os.path.join(FILE_PATH, 'cfd.log')
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
        return str(e)

def run_bg(cmd, logfile):
    with open(logfile, 'w') as f:
        subprocess.Popen(cmd, shell=True, stdout=f, stderr=f, stdin=subprocess.DEVNULL)

def get_arch():
    a = platform.machine().lower()
    return 'arm64' if ('arm' in a or 'aarch64' in a) else 'amd64'

def dl(name, url, retries=3):
    fp = os.path.join(FILE_PATH, name)
    if os.path.exists(fp): return True
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, stream=True, timeout=60)
            r.raise_for_status()
            with open(fp, 'wb') as f:
                for c in r.iter_content(8192): f.write(c)
            os.chmod(fp, 0o775)
            log(f'[DOWNLOAD] {name} downloaded', 2)
            return True
        except Exception as e:
            error(f'Download {name} attempt {attempt}/{retries} failed: {e}')
            try: os.remove(fp)
            except: pass
            if attempt < retries: time.sleep(5)
    return False

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...', flush=True)

    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm64' else 'https://amd64.ssss.nyc.mn'
    cfd_url = f'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}'

    # 下载 sing-box + cloudflared
    if not dl('web', f'{base}/sb'): return
    if not dl('cfd', cfd_url): return

    # 加载或生成 keypair
    pk = puk = None
    if os.path.exists(keypair_path):
        with open(keypair_path) as f:
            parts = f.read().strip().split('\n')[:2]
        if len(parts) >= 2:
            pk, puk = parts[0], parts[1]
            log('[KEY] Loaded existing keypair', 2)
        else:
            os.remove(keypair_path)
            pk = puk = None
    if not pk or not puk:
        kp = run(f'{web_path} generate reality-keypair')
        pm = re.search(r'PrivateKey:\s*(.*)', kp)
        pum = re.search(r'PublicKey:\s*(.*)', kp)
        if not (pm and pum): error('Failed to generate keypair'); return
        pk, puk = pm.group(1).strip(), pum.group(1).strip()
        with open(keypair_path, 'w') as f: f.write(f'{pk}\n{puk}\n')
        log('[KEY] Generated and saved', 2)

    # 证书
    run(f'openssl ecparam -genkey -name prime256v1 -out "{FILE_PATH}/private.key"')
    run(f'openssl req -new -x509 -days 3650 -key "{FILE_PATH}/private.key" -out "{FILE_PATH}/cert.pem" -subj "/CN=bing.com"')

    # 配置（hy2 + reality，同原版）
    config = {
        "log": {"disabled": True, "level": "info", "timestamp": True},
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
    with open(config_path, 'w') as f: json.dump(config, f, indent=2)
    log('[CONFIG] Generated', 2)

    # 启动 sing-box
    run(f'nohup {web_path} run -c {config_path} >/dev/null 2>&1 &')
    log('[SB] sing-box launched', 2)
    time.sleep(3)

    # ── 启动 Cloudflare Tunnel ──────────────────────────
    tunnel_url = ''
    if ARGO_TOKEN:
        # 长期隧道
        print('[ARGO] Starting permanent tunnel...')
        run_bg(f'nohup {cfd_path} tunnel run --token {ARGO_TOKEN} >{cfd_log} 2>&1 &', cfd_log)
        tunnel_url = f'https://{os.environ.get("ARGO_DOMAIN", "tunnel")}'
    else:
        # 临时隧道（默认）
        print('[ARGO] Starting temporary tunnel...')
        run_bg(f'nohup {cfd_path} tunnel --url http://localhost:{NODE_PORT} >{cfd_log} 2>&1 &', cfd_log)
        for _ in range(30):
            time.sleep(1)
            try:
                with open(cfd_log) as f:
                    m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', f.read())
                    if m: tunnel_url = m.group(0); break
            except: pass
        if not tunnel_url:
            error('Failed to get tunnel URL')
            return
    print(f'[ARGO] Tunnel: {tunnel_url}')

    # 获取 IP + ISP
    try: ip = requests.get('http://ipv4.ip.sb', timeout=5).text.strip()
    except: ip = '127.0.0.1'
    try:
        isp = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except:
        try: isp = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        except: isp = {}
    isp_str = f"{isp.get('country_code') or isp.get('countryCode', '')}-{isp.get('isp') or isp.get('org', 'Unknown')}".replace(' ', '_')

    # 节点链接
    host = tunnel_url.replace('https://', '').split('/')[0]
    nn = f'{NAME}-{isp_str}' if NAME and NAME.strip() else isp_str
    txt = (f'hysteria2://{UUID}@{host}:443/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#{nn}'
           f'\nvless://{UUID}@{host}:443?encryption=none&flow=xtls-rprx-vision&security=reality'
           f'&sni=www.iij.ad.jp&fp=chrome&pbk={puk}&type=tcp&headerType=none#{nn}')
    print(f'\n{txt}\n[INFO] Tunnel: {tunnel_url}')

    # TG 推送
    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': f'✅ 节点已就绪 | {nn}\n🌐 Argo: {host}\n\n<pre>{base64.b64encode(txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
        except: pass

    # HTTP 健康页
    s = HTTPServer(('0.0.0.0', int(os.environ.get('PORT') or '3000')), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()

    print('App running')
    while True: time.sleep(3600)

if __name__ == '__main__':
    main()