#!/usr/bin/env python3
"""sing-box-bot (max) — hy2+reality 直连 + Argo 隧道 + komari，全功能"""
import os, re, json, time, uuid, base64, platform, subprocess, threading, requests, sys, shutil, asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# ── 日志级别 ──────────────────────────────────────────
LOG_LEVEL = int(os.environ.get('LOG_LEVEL') or '0')
def log(msg, level=1):
    if LOG_LEVEL >= level: print(msg, flush=True)
def error(*args):
    print('[ERROR]', *args, file=sys.stderr, flush=True)

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
    error('NODE_PORT environment variable is required')
    sys.exit(1)
NODE_PORT = int(NODE_PORT_STR)
PORT = int(os.environ.get('PORT') or '3000')
NAME = os.environ.get('NAME') or ''
CHAT_ID = os.environ.get('CHAT_ID') or ''
BOT_TOKEN = os.environ.get('BOT_TOKEN') or ''
DAILY_RESTART = (os.environ.get('DAILY_RESTART') or 'false').lower() == 'true'
KOMARI_ENABLED = (os.environ.get('KOMARI_ENABLED') or 'true').lower() != 'false'
KOMARI_SERVER = os.environ.get('KOMARI_SERVER') or ''
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN') or ''
ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN') or ''
ARGO_AUTH = os.environ.get('ARGO_AUTH') or ''
ARGO_PORT = int(os.environ.get('ARGO_PORT') or '8001')
CFIP = os.environ.get('CFIP') or 'spring.io'
CFPORT = int(os.environ.get('CFPORT') or '443')

# ── 路径 ──────────────────────────────────────────────
img_path = os.path.join(FILE_PATH, 'img')       # sing-box（直连）
sod_path = os.path.join(FILE_PATH, 'sod')    # xray/v2ray（argo WS）
bot_path = os.path.join(FILE_PATH, 'bot')      # cloudflared
komari_path = os.path.join(FILE_PATH, 'komori')
komari_log = os.path.join(FILE_PATH, 'komori.log')
img_config = os.path.join(FILE_PATH, 'img.json')
sod_config = os.path.join(FILE_PATH, 'sod.json')
keypair_path = os.path.join(FILE_PATH, 'keypair.txt')

# ── HTTP 处理器 ──────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h2>sing-box-bot running</h2>')
    def log_message(self, *a): pass

# ── 工具 ──────────────────────────────────────────────
def run(cmd):
    try: r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30); return r.stdout + r.stderr
    except Exception as e: return str(e)

def run_check(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if r.returncode != 0: error(f'Command failed (code {r.returncode}): {cmd}\n{r.stderr}'); return False
        return True
    except Exception as e: error(f'Command error: {cmd}\n{e}'); return False

def get_arch():
    a = platform.machine().lower()
    return 'arm' if ('arm' in a or 'aarch64' in a) else 'amd'

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

def exec_cmd(command):
    try:
        p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        o, _ = p.communicate()
        return o
    except: return ''

# ── 主流程 ────────────────────────────────────────────
def main():
    print('App starting...', flush=True)

    log(f'=== sing-box-bot === Port: {NODE_PORT} (hy2 + reality + argo)', 2)
    if not os.path.exists(FILE_PATH): os.makedirs(FILE_PATH)
    if not os.path.exists(uuid_file):
        with open(uuid_file, 'w') as f: f.write(UUID)
        log('[UUID] Generated and saved', 2)
    else: log('[UUID] Loaded from file', 2)

    if DAILY_RESTART:
        threading.Timer(86400, lambda: os._exit(0)).start()
        log('[DAILY] Restart scheduled in 24h', 2)

    arch = get_arch()
    base = 'https://arm64.ssss.nyc.mn' if arch == 'arm' else 'https://amd64.ssss.nyc.mn'

    # 下载所有二进制
    files = [('img', f'{base}/sb'), ('sod', f'{base}/web'), ('bot', f'{base}/2go')]
    for name, url in files:
        if not dl(name, url): error(f'Failed to download {name}'); return

# ── Keypair + 证书 ──────────────────────────────────
    pk = puk = None
    if os.path.exists(keypair_path):
        with open(keypair_path) as f:
            parts = f.read().strip().split('\n')[:2]
        if len(parts) >= 2: pk, puk = parts[0], parts[1]
        else: os.remove(keypair_path)
    if not pk or not puk:
        kp = run(f'{img_path} generate reality-keypair')
        pm = re.search(r'PrivateKey:\s*(.*)', kp)
        pum = re.search(r'PublicKey:\s*(.*)', kp)
        if not (pm and pum): error('Failed to generate keypair'); return
        pk, puk = pm.group(1).strip(), pum.group(1).strip()
        with open(keypair_path, 'w') as f: f.write(f'{pk}\n{puk}\n')
        log('[KEY] Generated and saved', 2)
    if not run_check(f'openssl ecparam -genkey -name prime256v1 -out "{FILE_PATH}/private.key"'):
        error('openssl ecparam failed'); return
    if not run_check(f'openssl req -new -x509 -days 3650 -key "{FILE_PATH}/private.key" -out "{FILE_PATH}/cert.pem" -subj "/CN=bing.com"'):
        error('openssl req failed'); return

    # ── 直连配置（hy2 + reality，sing-box 格式）─────────────────
    sb_cfg = {
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
    with open(img_config, 'w') as f: json.dump(sb_cfg, f, indent=2)

    # ── Argo 配置（xray/v2ray 格式）────────────────────────
    xray_cfg = {"log":{"access":"/dev/null","error":"/dev/null","loglevel":"warning"},
    "inbounds":[
        {"port":ARGO_PORT,"protocol":"vless","settings":{"clients":[{"id":UUID}],"decryption":"none","fallbacks":[{"dest":3001},{"path":"/vless-argo","dest":3002},{"path":"/vmess-argo","dest":3003},{"path":"/trojan-argo","dest":3004}]},"streamSettings":{"network":"tcp"}},
        {"port":3001,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID}],"decryption":"none"},"streamSettings":{"network":"ws","security":"none"}},
        {"port":3002,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID,"level":0}],"decryption":"none"},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/vless-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}},
        {"port":3003,"listen":"127.0.0.1","protocol":"vmess","settings":{"clients":[{"id":UUID,"alterId":0}]},"streamSettings":{"network":"ws","wsSettings":{"path":"/vmess-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}},
        {"port":3004,"listen":"127.0.0.1","protocol":"trojan","settings":{"clients":[{"password":UUID}]},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/trojan-argo"}},"sniffing":{"enabled":True,"destOverride":["http","tls","quic"],"metadataOnly":False}}
    ],"outbounds":[{"protocol":"freedom","tag":"direct"},{"protocol":"blackhole","tag":"block"}]}
    with open(sod_config, 'w') as f: json.dump(xray_cfg, f, indent=2)
    log('[CONFIG] Generated', 2)

    # 启动 sing-box（直连）
    run(f'nohup {img_path} run -c {img_config} >/dev/null 2>&1 &')
    log('[IMG] sing-box launched', 2)

    # 启动 xray（argo WS）
    run(f'nohup {sod_path} -c {sod_config} >/dev/null 2>&1 &')
    log('[SOD] xray launched', 2)
    time.sleep(3)

    # 启动 komari
    if KOMARI_ENABLED and KOMARI_SERVER and KOMARI_TOKEN:
        log('[KOMARI] Starting in 5s...', 2)
        time.sleep(5)
        run_komari()
        threading.Thread(target=komari_watchdog, daemon=True).start()
        log('[KOMARI] Watchdog started (check every 5min)', 2)

    # 启动 Argo 隧道
    boot_log = os.path.join(FILE_PATH, 'boot.log')
    if ARGO_AUTH and ARGO_DOMAIN:
        if "TunnelSecret" in ARGO_AUTH:
            with open(os.path.join(FILE_PATH, 'tunnel.json'), 'w') as f: f.write(ARGO_AUTH)
            tid = ARGO_AUTH.split('"')[11]
            with open(os.path.join(FILE_PATH, 'tunnel.yml'), 'w') as f:
                f.write(f"tunnel: {tid}\ncredentials-file: {os.path.join(FILE_PATH, 'tunnel.json')}\nprotocol: http2\n")
                f.write(f"ingress:\n  - hostname: {ARGO_DOMAIN}\n    service: http://localhost:{ARGO_PORT}\n    originRequest:\n      noTLSVerify: true\n  - service: http_status:404\n")
            exec_cmd(f'nohup {bot_path} tunnel --edge-ip-version auto --config {os.path.join(FILE_PATH, "tunnel.yml")} run >/dev/null 2>&1 &')
        else:
            exec_cmd(f'nohup {bot_path} tunnel --edge-ip-version auto --no-autoupdate --protocol http2 run --token {ARGO_AUTH} >/dev/null 2>&1 &')
        log('[ARGO] Fixed tunnel started', 1)
        argo_domain = ARGO_DOMAIN
    else:
        exec_cmd(f'nohup {bot_path} tunnel --edge-ip-version auto --no-autoupdate --protocol http2 --logfile {boot_log} --loglevel info --url http://localhost:{ARGO_PORT} >/dev/null 2>&1 &')
        log('[ARGO] Temporary tunnel starting...', 1)
        argo_domain = None
        for _ in range(30):
            time.sleep(1)
            try:
                with open(boot_log) as f:
                    m = re.search(r'https?://([^ ]*trycloudflare\.com)/?', f.read())
                    if m: argo_domain = m.group(1); break
            except: pass
        if argo_domain: log(f'[ARGO] Tunnel: {argo_domain}', 1)

    # 获取 IP + ISP
    try: ip = requests.get('http://ipv4.ip.sb', timeout=5).text.strip()
    except: ip = '127.0.0.1'
    try: isp = requests.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
    except:
        try: isp = requests.get('http://ip-api.com/json/', headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).json()
        except: isp = {}
    isp_str = f"{isp.get('country_code') or isp.get('countryCode', '')}-{isp.get('isp') or isp.get('org', 'Unknown')}".replace(' ', '_')
    nn = f'{NAME}-{isp_str}' if NAME and NAME.strip() else isp_str

    # 直连节点
    txt_direct = (f'hysteria2://{UUID}@{ip}:{NODE_PORT}/?sni=www.bing.com&insecure=1&alpn=h3&obfs=none#{nn}'
                  f'\nvless://{UUID}@{ip}:{NODE_PORT}?encryption=none&flow=xtls-rprx-vision&security=reality'
                  f'&sni=www.iij.ad.jp&fp=chrome&pbk={puk}&type=tcp&headerType=none#{nn}')
    log(f'\n{txt_direct}\n[INFO] Direct Port: {NODE_PORT}', 1)

    # Argo 节点
    if argo_domain:
        VMESS = {"v":"2","ps":f"{nn}","add":CFIP,"port":CFPORT,"id":UUID,"aid":"0","scy":"none","net":"ws","type":"none","host":argo_domain,"path":"/vmess-argo?ed=2560","tls":"tls","sni":argo_domain,"alpn":"","fp":"chrome"}
        txt_argo = (f'vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{nn}'
                    f'\nvmess://{base64.b64encode(json.dumps(VMESS).encode()).decode()}'
                    f'\ntrojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{nn}')
        log(f'\n{txt_argo}\n[INFO] Argo: {argo_domain}', 1)

    # TG 推送（直连 + argo）
    if BOT_TOKEN and CHAT_ID:
        all_txt = txt_direct
        if argo_domain: all_txt += '\n' + txt_argo
        msg = f'✅ 节点已就绪 | {nn}\n🌍 IP: {ip}'
        if argo_domain: msg += f'\n🌐 Argo: {argo_domain}'
        try:
            requests.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                          params={'chat_id': CHAT_ID, 'text': msg + f'\n\n<pre>{base64.b64encode(all_txt.encode()).decode()}</pre>', 'parse_mode': 'HTML'}, timeout=15)
            log('[TG] Sent', 2)
        except Exception as e: error(f'[TG] Failed: {e}')

    if UPLOAD_URL:
        try:
            nodes = [l for l in txt_direct.split('\n') if l.strip()]
            if argo_domain: nodes += [l for l in txt_argo.split('\n') if l.strip()]
            requests.post(f'{UPLOAD_URL}/api/add-nodes', json={"nodes": nodes},
                          headers={"Content-Type": "application/json"}, timeout=15)
            log('[UPLOAD] Nodes uploaded', 2)
        except: pass

    if AUTO_ACCESS and PROJECT_URL:
        try:
            requests.post('https://keep.gvrander.eu.org/add-url', json={"url": PROJECT_URL},
                          headers={"Content-Type": "application/json"}, timeout=15)
        except: pass

    # HTTP 健康页
    s = HTTPServer(('0.0.0.0', PORT), Handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    log(f'[HTTP] Listening on :{PORT}', 2)

    # 90s 清理
    def cleanup():
        time.sleep(90)
        for f in [img_config, sod_config, img_path, sod_path, bot_path, boot_log, os.path.join(FILE_PATH, 'list.txt')]:
            try:
                if os.path.exists(f):
                    os.remove(f) if not os.path.isdir(f) else shutil.rmtree(f)
            except: pass
        print('\033c', end='')
        print('App running')
        log('[CLEANUP] Temporary files removed, app is fully running', 3)
    threading.Timer(90, cleanup).start()

    while True: time.sleep(3600)

# ── komari ──────────────────────────────────────────────
def run_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    ka = next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)
    if not ka: return
    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    if not os.path.exists(komari_path):
        if not dl('komori', url): return
    run(f'nohup {komari_path} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{komari_log} 2>&1 &')
    log('[KOMARI] Started', 2)

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
    if not komari_alive():
        log('[KOMARI] Process not found, restarting...', 2)
        run_komari()
    threading.Timer(300, komari_watchdog).start()

if __name__ == '__main__':
    main()