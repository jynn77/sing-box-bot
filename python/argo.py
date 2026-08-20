import os, re, json, time, base64, shutil, asyncio, requests, platform, subprocess, threading
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer

# ── 从 .env 加载 ──────────────────────────────────────
_env = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env):
    for l in open(_env):
        m = re.match(r'^\s*([^#=]+)=(.*)', l.strip())
        if m: os.environ.setdefault(m.group(1).strip(), m.group(2).strip().strip('"\''))

# ── 环境变量 ──────────────────────────────────────────
UPLOAD_URL = os.environ.get('UPLOAD_URL', '')
PROJECT_URL = os.environ.get('PROJECT_URL', '')
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', 'false').lower() == 'true'
FILE_PATH = os.environ.get('FILE_PATH', '.cache')
SUB_PATH = os.environ.get('SUB_PATH', 'sub')
UUID = os.environ.get('UUID', '6c8ec4c2-0ebd-6341-bedc-1c741c6e5506')
KOMARI_SERVER = os.environ.get('KOMARI_SERVER', '')
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN', '')
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', '')
ARGO_AUTH = os.environ.get('ARGO_AUTH', '')
ARGO_PORT = int(os.environ.get('ARGO_PORT', '8001'))
CFIP = os.environ.get('CFIP', 'mfa.gov.ua')
CFPORT = int(os.environ.get('CFPORT', '8443'))
NAME = os.environ.get('NAME', '')
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)

# ── 路径 ──────────────────────────────────────────────
web_path = os.path.join(FILE_PATH, 'web')
bot_path = os.path.join(FILE_PATH, 'bot')
sub_path = os.path.join(FILE_PATH, 'sub.txt')
list_path = os.path.join(FILE_PATH, 'list.txt')
boot_log_path = os.path.join(FILE_PATH, 'boot.log')
config_path = os.path.join(FILE_PATH, 'config.json')
komori_path = os.path.join(FILE_PATH, 'komori')
komori_log = os.path.join(FILE_PATH, 'komori.log')

# ── 工具 ──────────────────────────────────────────────
def create_directory():
    print('\033c', end='')
    if not os.path.exists(FILE_PATH):
        os.makedirs(FILE_PATH)
        print(f"{FILE_PATH} is created")
    else:
        print(f"{FILE_PATH} already exists")

def get_arch():
    a = platform.machine().lower()
    return 'arm' if ('arm' in a or 'aarch64' in a) else 'amd'

def download_file(file_name, file_url):
    fp = os.path.join(FILE_PATH, file_name)
    try:
        r = requests.get(file_url, stream=True)
        r.raise_for_status()
        with open(fp, 'wb') as f:
            for c in r.iter_content(8192): f.write(c)
        print(f"Download {file_name} successfully")
        return True
    except Exception as e:
        if os.path.exists(fp): os.remove(fp)
        print(f"Download {file_name} failed: {e}")
        return False

def authorize_files(file_paths):
    for f in file_paths:
        p = os.path.join(FILE_PATH, f)
        if os.path.exists(p):
            try: os.chmod(p, 0o775); print(f"Empowerment success for {p}: 775")
            except Exception as e: print(f"Empowerment failed for {p}: {e}")

def exec_cmd(command):
    try:
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        o, _ = p.communicate()
        return o
    except Exception as e:
        print(f"Error executing command: {e}")
        return str(e)

# ── HTTP ──────────────────────────────────────────────
class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Hello World')
        elif self.path == f'/{SUB_PATH}':
            try:
                with open(sub_path, 'rb') as f: c = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(c)
            except:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a): pass

# ── Argo ──────────────────────────────────────────────
def argo_type():
    if not ARGO_AUTH or not ARGO_DOMAIN:
        print("ARGO_DOMAIN or ARGO_AUTH variable is empty, use quick tunnels")
        return
    if "TunnelSecret" in ARGO_AUTH:
        with open(os.path.join(FILE_PATH, 'tunnel.json'), 'w') as f: f.write(ARGO_AUTH)
        tid = ARGO_AUTH.split('"')[11]
        with open(os.path.join(FILE_PATH, 'tunnel.yml'), 'w') as f:
            f.write(f"""tunnel: {tid}
credentials-file: {os.path.join(FILE_PATH, 'tunnel.json')}
protocol: http2
ingress:
  - hostname: {ARGO_DOMAIN}
    service: http://localhost:{ARGO_PORT}
    originRequest:
      noTLSVerify: true
  - service: http_status:404
""")
    else:
        print("Use token connect to tunnel,please set the {ARGO_PORT} in cloudflare")

# ── komari ──────────────────────────────────────────────
def komari_arch():
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    return next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)

def start_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    ka = komari_arch()
    if not ka: return
    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    if not os.path.exists(komori_path):
        if not download_file('komori', url): return
    exec_cmd(f'nohup {komori_path} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{komori_log} 2>&1 &')
    print('komori is running')

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
    while True:
        time.sleep(300)
        if not komari_alive():
            print('[KOMARI] Restarting...')
            start_komari()

# ── 下载并运行 ────────────────────────────────────────
async def download_files_and_run():
    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm' else 'https://amd64.ssss.nyc.mn'
    cf_arch = 'arm64' if arch == 'arm' else 'amd64'
    files = [
        {"fileName": "web", "fileUrl": f"{base}/web"},
        {"fileName": "bot", "fileUrl": f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{cf_arch}"}
    ]
    for f in files:
        if not download_file(f["fileName"], f["fileUrl"]):
            print("Error downloading files")
            return
    authorize_files(['web', 'bot'])

    # 生成配置
    config = {"log":{"access":"/dev/null","error":"/dev/null","loglevel":"none"},
    "inbounds":[
        {"port":ARGO_PORT,"protocol":"vless","settings":{"clients":[{"id":UUID,"flow":"xtls-rprx-vision"}],"decryption":"none","fallbacks":[{"dest":3001},{"path":"/vless-argo","dest":3002},{"path":"/vmess-argo","dest":3003},{"path":"/trojan-argo","dest":3004}]},"streamSettings":{"network":"tcp"}},
        {"port":3001,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID}],"decryption":"none"},"streamSettings":{"network":"ws","security":"none"}},
        {"port":3002,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID,"level":0}],"decryption":"none"},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/vless-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}},
        {"port":3003,"listen":"127.0.0.1","protocol":"vmess","settings":{"clients":[{"id":UUID,"alterId":0}]},"streamSettings":{"network":"ws","wsSettings":{"path":"/vmess-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}},
        {"port":3004,"listen":"127.0.0.1","protocol":"trojan","settings":{"clients":[{"password":UUID}]},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/trojan-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}}
    ],"outbounds":[{"protocol":"freedom","tag":"direct"},{"protocol":"blackhole","tag":"block"}]}
    with open(config_path, 'w', encoding='utf-8') as f: json.dump(config, f, ensure_ascii=False, indent=2)

    # 启动 komari
    if KOMARI_SERVER and KOMARI_TOKEN:
        start_komari()
        threading.Thread(target=komari_watchdog, daemon=True).start()

    # 启动 web
    exec_cmd(f'nohup {web_path} -c {config_path} >/dev/null 2>&1 &')
    print('web is running')
    time.sleep(1)

    # 启动 cloudflared
    if os.path.exists(bot_path):
        if re.match(r'^[A-Z0-9a-z=]{120,250}$', ARGO_AUTH):
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH}"
        elif "TunnelSecret" in ARGO_AUTH:
            args = f"tunnel --edge-ip-version auto --config {os.path.join(FILE_PATH, 'tunnel.yml')} run"
        else:
            args = f"tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {boot_log_path} --loglevel info --url http://localhost:{ARGO_PORT}"
        exec_cmd(f'nohup {bot_path} {args} >/dev/null 2>&1 &')
        print('bot is running')
        time.sleep(2)

    time.sleep(5)
    await extract_domains()

# ── 提取域名 ──────────────────────────────────────────
async def extract_domains():
    if ARGO_AUTH and ARGO_DOMAIN:
        print(f'ARGO_DOMAIN: {ARGO_DOMAIN}')
        await generate_links(ARGO_DOMAIN)
    else:
        try:
            with open(boot_log_path) as f: content = f.read()
            m = re.search(r'https?://([^ ]*trycloudflare\.com)/?', content)
            if m:
                d = m.group(1)
                print(f'ArgoDomain: {d}')
                await generate_links(d)
            else:
                print('ArgoDomain not found, restarting bot...')
                if os.path.exists(boot_log_path): os.remove(boot_log_path)
                try: exec_cmd('pkill -f "[b]ot" > /dev/null 2>&1')
                except: pass
                time.sleep(1)
                exec_cmd(f'nohup {bot_path} tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {boot_log_path} --loglevel info --url http://localhost:{ARGO_PORT} >/dev/null 2>&1 &')
                print('bot is running.')
                time.sleep(6)
                await extract_domains()
        except Exception as e: print(f'Error reading boot.log: {e}')

# ── 生成链接 ──────────────────────────────────────────
async def generate_links(argo_domain):
    try:
        geo = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        cc = geo.get('country_code', 'Unknown')
        isp = geo.get('isp', 'Unknown').replace(' ', '_').strip()
    except:
        try:
            geo = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
            if geo.get('status') == 'success':
                cc = geo.get('countryCode', 'Unknown')
                isp = geo.get('org', 'Unknown').replace(' ', '_').strip()
            else: cc, isp = 'Unknown', 'Unknown'
        except: cc, isp = 'Unknown', 'Unknown'
    ISP = f"{NAME.strip()}-{cc}_{isp}" if NAME and NAME.strip() else f"{cc}_{isp}"

    time.sleep(2)
    VMESS = {"v":"2","ps":f"{ISP}","add":CFIP,"port":CFPORT,"id":UUID,"aid":"0","scy":"none","net":"ws","type":"none","host":argo_domain,"path":"/vmess-argo?ed=2560","tls":"tls","sni":argo_domain,"alpn":"","fp":"chrome"}
    list_txt = f"""vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{ISP}

vmess://{base64.b64encode(json.dumps(VMESS).encode()).decode()}

trojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{ISP}"""

    with open(list_path, 'w', encoding='utf-8') as f: f.write(list_txt)
    sub_txt = base64.b64encode(list_txt.encode('utf-8')).decode('utf-8')
    with open(sub_path, 'w', encoding='utf-8') as f: f.write(sub_txt)
    print(sub_txt)
    print(f"{FILE_PATH}/sub.txt saved successfully")
    send_telegram()
    upload_nodes()
    return sub_txt

# ── 上传节点 ──────────────────────────────────────────
def upload_nodes():
    if UPLOAD_URL and PROJECT_URL:
        try:
            r = requests.post(f"{UPLOAD_URL}/api/add-subscriptions", json={"subscription": [f"{PROJECT_URL}/{SUB_PATH}"]}, headers={"Content-Type": "application/json"}, timeout=15)
            if r.status_code == 200: print('Subscription uploaded successfully')
        except: pass
    elif UPLOAD_URL:
        if not os.path.exists(list_path): return
        with open(list_path) as f: content = f.read()
        nodes = [l for l in content.split('\n') if any(p in l for p in ['vless://', 'vmess://', 'trojan://', 'hysteria2://', 'tuic://'])]
        if not nodes: return
        try:
            requests.post(f"{UPLOAD_URL}/api/add-nodes", data=json.dumps({"nodes": nodes}), headers={"Content-Type": "application/json"}, timeout=15)
        except: pass

# ── TG 推送 ──────────────────────────────────────────
def send_telegram():
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        with open(sub_path) as f: msg = f.read()
        en = re.sub(r'([_*\[\]()~>#+=|{}.!\-])', r'\\\1', NAME)
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      params={"chat_id": CHAT_ID, "text": f"**{en}节点推送通知**\n{msg}", "parse_mode": "MarkdownV2"})
        print('Telegram message sent successfully')
    except Exception as e: print(f'Failed to send Telegram message: {e}')

# ── 自动保活 ──────────────────────────────────────────
def add_visit_task():
    if not AUTO_ACCESS or not PROJECT_URL: return
    try:
        requests.post('https://keep.gvrander.eu.org/add-url', json={"url": PROJECT_URL}, headers={"Content-Type": "application/json"}, timeout=15)
        print('automatic access task added successfully')
    except Exception as e: print(f'Failed to add URL: {e}')

# ── 清理 ──────────────────────────────────────────────
def clean_files():
    def _cleanup():
        time.sleep(90)
        for f in [boot_log_path, config_path, list_path, web_path, bot_path]:
            try:
                if os.path.exists(f):
                    os.remove(f) if not os.path.isdir(f) else shutil.rmtree(f)
            except: pass
        print('\033c', end='')
        print('App is running')
        print('Thank you for using this script, enjoy!')
    threading.Thread(target=_cleanup, daemon=True).start()

# ── 主流程 ────────────────────────────────────────────
async def start_server():
    create_directory()
    argo_type()
    await download_files_and_run()
    add_visit_task()
    Thread(target=lambda: HTTPServer(('0.0.0.0', PORT), RequestHandler).serve_forever(), daemon=True).start()
    print(f"Server is running on port {PORT}")
    clean_files()

def run_async():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server())
    while True: time.sleep(3600)

if __name__ == "__main__":
    run_async()