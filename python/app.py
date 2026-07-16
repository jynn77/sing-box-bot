import os, re, json, time, uuid, base64, platform, subprocess, threading, requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv()

# ── 环境变量 ──────────────────────────────────────────
UPLOAD_URL = os.environ.get('UPLOAD_URL') or ''
PROJECT_URL = os.environ.get('PROJECT_URL') or ''
AUTO_ACCESS = (os.environ.get('AUTO_ACCESS') or 'false').lower() == 'true'
FILE_PATH = os.environ.get('FILE_PATH') or '.cache'
uuid_file = os.path.join(FILE_PATH, 'uuid.txt')
UUID = os.environ.get('UUID') or (
    open(uuid_file).read().strip() if os.path.exists(uuid_file) else None
) or str(uuid.uuid4())
NODE_PORT_STR = os.environ.get('NODE_PORT')
if not NODE_PORT_STR:
    print('[FATAL] NODE_PORT is required (e.g. NODE_PORT=25983)')
    exit(1)
NODE_PORT = int(NODE_PORT_STR)
PORT = int(os.environ.get('PORT') or '3000')
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
        print(f'[DL] {name} downloaded'); return True
    except Exception as e:
        try: os.remove(fp)
        except: pass
        print(f'[DL] {name} failed: {e}'); return False

# ── 主流程 ────────────────────────────────────────────
def main():
    print(f'=== sing-box-bot === Port: {NODE_PORT} (hy2 + reality)')
    if not os.path.exists(FILE_PATH): os.makedirs(FILE_PATH)
    if not os.path.exists(uuid_file):
        with open(uuid_file, 'w') as f: f.write(UUID)
        print(f'[UUID] Generated and saved')
    else:
        print(f'[UUID] Loaded from file')
    if DAILY_RESTART:
        threading.Timer(86400, lambda: os._exit(0)).start()
        print('[DAILY] Restart scheduled in 24h')

    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm' else 'https://amd64.ssss.nyc.mn'
    if not dl('web', f'{base}/sb'): print('[FATAL] Download failed'); return

    # 加载或生成 reality keypair（持久化，重启不变）
    if os.path.exists(keypair_path):
        with open(keypair_path) as f:
            pk, puk = f.read().strip().split('\n')[:2]
        print(f'[KEY] Loaded existing keypair')
    else:
        kp = run(f'{web_path} generate reality-keypair')
        pm = re.search(r'PrivateKey:\s*(.*)', kp)
        pum = re.search(r'PublicKey:\s*(.*)', kp)
        if not (pm and pum): print('[FATAL] Failed to extract keypair'); return
        pk, puk = pm.group(1).strip(), pum.group(1).strip()
        with open(keypair_path, 'w') as f: f.write(f'{pk}\n{puk}\n')
        print(f'[KEY] Generated and saved')
    print(f'Private Key: {pk}\nPublic Key: {puk}')

    run(f'openssl ecparam -genkey -name prime256v1 -out "{FILE_PATH}/private.key"')
    run(f'openssl req -new -x509 -days 3650 -key "{FILE_PATH}/private.key" -out "{FILE_PATH}/cert.pem" -subj "/CN=bing.com"')

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
    print('[CONFIG] Generated')

    run(f'nohup {web_path} run -c {config_path} >/dev/null 2>&1 &')
    print('[SB] sing-box running')
    time.sleep(3)

    if KOMARI_ENABLED:
        print('[KOMARI] Starting in 5s...'); time.sleep(5); run_komari()
        threading.Thread(target=komari_watchdog, daemon=True).start()
        print('[KOMARI] Watchdog started (check every 5min)')

    # 获取 IP + ISP
    try: ip = requests.get('http://ipv4.ip.sb', timeout=5).text.strip()
    except: ip = '127.0.0.1'
    try: isp = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except:
        try: isp = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        except: isp = {}
    isp_str = f"{isp.get('country_code') or isp.get('countryCode', '')}-{isp.get('isp') or isp.get('org', 'Unknown')}".replace(' ', '_')

    nn = f'{NAME}-{isp_str}' if NAME and NAME.strip() else isp_str
    txt = (f'hysteria2://{UUID}@{ip}:{NODE_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#{nn}'
           f'\nvless://{UUID}@{ip}:{NODE_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality'
           f'&sni=www.iij.ad.jp&fp=chrome&pbk={puk}&type=tcp&headerType=none#{nn}')
    print(f'\n{txt}\n[INFO] Port: {NODE_PORT}')

    if BOT_TOKEN and CHAT_ID:
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': f'✅ 节点已就绪 | {nn}\n🌍 IP: {ip}\n\n<pre>{base64.b64encode(txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
            print('[TG] Sent')
        except Exception as e: print(f'[TG] Failed: {e}')
    if UPLOAD_URL:
        try:
            requests.post(f'{UPLOAD_URL}/api/add-nodes', json={"nodes": [l for l in txt.split("\n") if l.strip()]},
                          headers={"Content-Type": "application/json"}, timeout=15)
            print('[UPLOAD] Nodes uploaded')
        except: pass
    if AUTO_ACCESS and PROJECT_URL:
        try:
            requests.post('https://keep.gvrander.eu.org/add-url', json={"url": PROJECT_URL},
                          headers={"Content-Type": "application/json"}, timeout=15)
            print('[VISIT] Auto access task added')
        except Exception as e: print(f'[VISIT] Failed: {e}')

    # HTTP
    s = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'[HTTP] :{PORT}')
    threading.Thread(target=s.serve_forever, daemon=True).start()

    # 90s 清理
    threading.Timer(90, lambda: (
        [os.remove(f) for f in [config_path, web_path] if os.path.exists(f)],
        print('\033c', end=''), print('[DONE] App is running')
    )).start()

    while True: time.sleep(3600)

# ── komari-agent ──────────────────────────────────────
def run_komari():
    a = platform.machine().lower()
    arch_map = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    ka = next((v for k, v in arch_map.items() if k in a), None)
    if not ka and a.startswith('arm'): ka = 'arm'
    if not ka: print(f'[KOMARI] Unsupported arch: {a}, skip'); return

    if not dl('komori', f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'): return

    run(f'nohup {komari_path} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{komari_log} 2>&1 &')
    time.sleep(2)
    if os.path.exists(komari_log) and os.path.getsize(komari_log) > 0:
        lines = open(komari_log).read().strip().split('\n')[-3:]
        print(f'[KOMARI] Started, log: {komari_log}')
        for l in lines: print(f'  {l}')
    else:
        print(f'[KOMARI] No log yet: {komari_log}')

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
        print('[KOMARI] Process not found, restarting...')
        run_komari()
    threading.Timer(300, komari_watchdog).start()

if __name__ == '__main__':
    main()