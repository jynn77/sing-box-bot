import os, re, json, time, uuid, base64, platform, subprocess, threading, requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv()

# ── 环境变量 ──────────────────────────────────────────
UPLOAD_URL = os.environ.get('UPLOAD_URL') or ''
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
uuid_file = os.path.join(FILE_PATH, 'uuid.txt')
UUID = os.environ.get('UUID') or (
    open(uuid_file).read().strip() if os.path.exists(uuid_file) else None
) or str(uuid.uuid4())
NODE_PORT_STR = os.environ.get('NODE_PORT')
if not NODE_PORT_STR:
    exit(1)
NODE_PORT = int(NODE_PORT_STR)
PORT = int(os.environ.get('PORT') or '3001')
NAME = os.environ.get('NAME') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
DAILY_RESTART = (os.environ.get('DAILY_RESTART') or 'false').lower() == 'true'
KOMARI_ENABLED = (os.environ.get('KOMARI_ENABLED') or 'true').lower() != 'false'
KOMARI_SERVER = os.environ.get('KOMARI_SERVER') or ''
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN') or ''
SERVER_ADDR = os.environ.get('SERVER_ADDR') or ''

# ── 路径 ──────────────────────────────────────────────
web_path = os.path.join(FILE_PATH, 'web')
komari_path = os.path.join(FILE_PATH, 'komori')
komari_log = os.path.join(FILE_PATH, 'komori.log')
config_path = os.path.join(FILE_PATH, 'config.json')

# ── HTTP 处理器 ──────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f'<h2>sing-box-bot running</h2><p>vless-ws port: {NODE_PORT}</p>'.encode())
    def log_message(self, *a): pass

# ── 工具 ──────────────────────────────────────────────
def run(cmd):
    try: r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30); return r.stdout + r.stderr
    except Exception as e: return str(e)

def get_arch():
    a = platform.machine().lower()
    return 'arm' if ('arm' in a or 'aarch64' in a) else 'amd'

def dl(name, url):
    fp = os.path.join(FILE_PATH, name)
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(fp, 'wb') as f:
            for c in r.iter_content(8192): f.write(c)
        os.chmod(fp, 0o775)
        return True
    except Exception as e:
        try: os.remove(fp)
        except: pass
        return False

# ── 主流程 ────────────────────────────────────────────
def main():
    if not os.path.exists(FILE_PATH): os.makedirs(FILE_PATH)
    if not os.path.exists(uuid_file):
        with open(uuid_file, 'w') as f: f.write(UUID)
    if DAILY_RESTART:
        threading.Timer(86400, lambda: os._exit(0)).start()

    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm' else 'https://amd64.ssss.nyc.mn'
    if not dl('web', f'{base}/sb'): return

    # sing-box 配置：vless + WebSocket，TLS 由 zerops 代理层处理
    config = {
        "log": {"disabled": True, "level": "info", "timestamp": True},
        "inbounds": [{
            "tag": "vless-ws-in", "type": "vless",
            "listen": "::", "listen_port": NODE_PORT,
            "users": [{"uuid": UUID}],
            "transport": {"type": "ws", "path": "/vless"}
        }, {
            "tag": "trojan-ws", "type": "trojan",
            "listen": "::", "listen_port": NODE_PORT,
            "users": [{"password": UUID}],
            "transport": {"type": "ws", "path": "/trojan"}
        }, {
            "tag": "ss-ws", "type": "shadowsocks",
            "listen": "::", "listen_port": NODE_PORT,
            "method": "chacha20-ietf-poly1305", "password": UUID,
            "transport": {"type": "ws", "path": "/ss"}
        }],
        "outbounds": [{"type": "direct", "tag": "direct"}]}
    with open(config_path, 'w') as f: json.dump(config, f, indent=2)

    run(f'nohup {web_path} run -c {config_path} >/dev/null 2>&1 &')
    time.sleep(3)

    if KOMARI_ENABLED:
        time.sleep(5); run_komari()
        threading.Thread(target=komari_watchdog, daemon=True).start()

    # 节点链接
    if SERVER_ADDR:
        ip = SERVER_ADDR
        isp_str = 'Zerops'
    else:
        try: ip = requests.get('http://ipv4.ip.sb', timeout=5).text.strip()
        except: ip = '127.0.0.1'
        try: isp = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        except:
            try: isp = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            except: isp = {}
        isp_str = f"{isp.get('country_code') or isp.get('countryCode', '')}-{isp.get('isp') or isp.get('org', 'Unknown')}".replace(' ', '_')

    nn = f'{NAME}-{isp_str}' if NAME and NAME.strip() else isp_str
    ss_ui = base64.urlsafe_b64encode(f'chacha20-ietf-poly1305:{UUID}'.encode()).decode().rstrip('=')
    txt = '\n'.join(filter(None, [
        f'vless://{UUID}@{ip}:443?type=ws&path=%2Fvless&security=tls&sni={ip}&fp=chrome#{nn}',
        f'trojan://{UUID}@{ip}:443?type=ws&path=%2Ftrojan&security=tls&sni={ip}#{nn}',
        f'ss://{ss_ui}@{ip}:443?type=ws&path=%2Fss&security=tls#{nn}',
    ]))

    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': f'✅ 节点已就绪 | {nn}\n🌍 IP: {ip}\n\n<pre>{base64.b64encode(txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
        except: pass
    if UPLOAD_URL:
        try:
            requests.post(f'{UPLOAD_URL}/api/add-nodes', json={"nodes": [l for l in txt.split("\n") if l.strip()]},
                          headers={"Content-Type": "application/json"}, timeout=15)
        except: pass

    # HTTP 健康页
    s = HTTPServer(('0.0.0.0', PORT), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()

    # 90s 清理
    threading.Timer(90, lambda: (
        [os.remove(f) for f in [config_path, web_path] if os.path.exists(f)]
    )).start()

    while True: time.sleep(3600)

# ── komari-agent ──────────────────────────────────────
def run_komari():
    a = platform.machine().lower()
    arch_map = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    ka = next((v for k, v in arch_map.items() if k in a), None)
    if not ka and a.startswith('arm'): ka = 'arm'
    if not ka: return

    if not dl('komori', f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'): return

    run(f'nohup {komari_path} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{komari_log} 2>&1 &')
    time.sleep(2)

def komari_alive():
    try:
        subprocess.run(['pgrep', '-f', 'komori'], capture_output=True, check=True, timeout=5)
        return True
    except: pass
    try:
        r = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=5)
        return 'komori' in r.stdout
    except: return True

def komari_watchdog():
    if KOMARI_ENABLED and not komari_alive():
        run_komari()
    threading.Timer(300, komari_watchdog).start()

if __name__ == '__main__':
    main()