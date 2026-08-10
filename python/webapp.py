#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webapp - 纯 Python WebSocket 代理（VLESS/Trojan/SS）+ komari"""
import os, sys, socket, struct, hashlib, base64, asyncio, aiohttp, logging, ipaddress, subprocess, threading, re, time, platform, urllib.request, stat, uuid
from aiohttp import web
from pathlib import Path

# ── 从 .env 加载 ──────────────────────────────────────
_env = Path(__file__).parent / '.env'
if not _env.exists(): _env = Path('.env')
if _env.exists():
    for l in _env.read_text().split('\n'):
        m = re.match(r'^\s*([^#=]+)=(.*)', l.strip())
        if m: os.environ.setdefault(m.group(1).strip(), m.group(2).strip().strip('"\''))

# ── 环境变量 ──────────────────────────────────────────
FILE_PATH = os.environ.get('FILE_PATH', '.cache')
UUID = os.environ.get('UUID') or (lambda f: open(f).read().strip() if os.path.exists(f) else None)(os.path.join(FILE_PATH, 'uuid.txt')) or str(uuid.uuid4())
DOMAIN = os.environ.get('DOMAIN', '').replace('https://', '').replace('http://', '').rstrip('/')
NAME = os.environ.get('NAME', '')
WSPATH = os.environ.get('WSPATH', UUID[:8])
LOG_LEVEL = int(os.environ.get('LOG_LEVEL') or '0')
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
KOMARI_SERVER = os.environ.get('KOMARI_SERVER', '')
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN', '')

# ── 日志 ──────────────────────────────────────────────
log_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
logging.basicConfig(level=log_levels.get(LOG_LEVEL, logging.WARNING),
    format='%(asctime)s - %(levelname)s - %(message)s')
for name in ['aiohttp.access', 'aiohttp.server', 'aiohttp.client', 'aiohttp.internal', 'aiohttp.websocket']:
    logging.getLogger(name).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── 全局变量 ──────────────────────────────────────────
CurrentDomain = DOMAIN
CurrentPort = 443
Tls = 'tls'
ISP = ''

# ── 工具 ──────────────────────────────────────────────
DNS_SERVERS = ['8.8.4.4', '1.1.1.1']
BLOCKED_DOMAINS = ['speedtest.net', 'fast.com', 'speedtest.cn', 'speed.cloudflare.com', 'speedof.me',
    'testmy.net', 'bandwidth.place', 'speed.io', 'librespeed.org', 'speedcheck.org']

def is_port_available(port, host='0.0.0.0'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try: s.bind((host, port)); return True
        except OSError: return False

def find_available_port(start_port, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port): return port
    return None

def is_blocked_domain(host):
    if not host: return False
    hl = host.lower()
    return any(hl == b or hl.endswith('.' + b) for b in BLOCKED_DOMAINS)

async def get_isp():
    global ISP
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get('https://api.ip.sb/geoip', headers={'User-Agent': 'Mozilla/5.0'}, timeout=3) as r:
                if r.status == 200:
                    d = await r.json(); ISP = f"{d.get('country_code','')}-{d.get('isp','')}".replace(' ','_'); return
    except: pass
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get('http://ip-api.com/json', headers={'User-Agent': 'Mozilla/5.0'}, timeout=3) as r:
                if r.status == 200:
                    d = await r.json(); ISP = f"{d.get('countryCode','')}-{d.get('org','')}".replace(' ','_'); return
    except: pass
    ISP = 'Unknown'

async def get_ip():
    global CurrentDomain, Tls, CurrentPort
    if not DOMAIN or DOMAIN == 'your-domain.com':
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get('https://api-ipv4.ip.sb/ip', timeout=5) as r:
                    if r.status == 200:
                        CurrentDomain = (await r.text()).strip(); Tls = 'none'; CurrentPort = PORT
        except:
            CurrentDomain = 'change-your-domain.com'; Tls = 'tls'; CurrentPort = 443
    else:
        CurrentDomain = DOMAIN; Tls = 'tls'; CurrentPort = 443

async def resolve_host(host):
    try:
        ipaddress.ip_address(host); return host
    except: pass
    for dns in DNS_SERVERS:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f'https://dns.google/resolve?name={host}&type=A', timeout=5) as r:
                    if r.status == 200:
                        data = await r.json()
                        if data.get('Status') == 0 and data.get('Answer'):
                            for a in data['Answer']:
                                if a.get('type') == 1: return a.get('data')
        except: continue
    return host

# ── TG 推送 ──────────────────────────────────────────
async def send_tg(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post(f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
                params={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}, timeout=15)
        logger.info('TG sent')
    except: pass

# ── komari ──────────────────────────────────────────────
def komari_arch():
    a = platform.machine().lower()
    m = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64', 'arm64': 'arm64'}
    return next((v for k, v in m.items() if k in a), None) or ('arm' if a.startswith('arm') else None)

def start_komari():
    if not KOMARI_SERVER or not KOMARI_TOKEN: return
    ka = komari_arch()
    if not ka: return
    os.makedirs(FILE_PATH, exist_ok=True)
    kp = os.path.join(FILE_PATH, 'komori')
    kl = os.path.join(FILE_PATH, 'komori.log')
    url = f'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{ka}'
    if not os.path.exists(kp):
        try:
            opener = urllib.request.build_opener()
            opener.addheaders = [('User-Agent', 'Mozilla/5.0'), ('Accept', '*/*')]
            urllib.request.install_opener(opener)
            urllib.request.urlretrieve(url, kp)
            os.chmod(kp, os.stat(kp).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except: return
    subprocess.Popen(f'nohup {kp} -e {KOMARI_SERVER} --auto-discovery {KOMARI_TOKEN} >{kl} 2>&1 &', shell=True)
    logger.info('[KOMARI] Started')

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
            logger.info('[KOMARI] Restarting...')
            start_komari()

# ── 代理处理（原版代码，未改动）─────────────────────────
class ProxyHandler:
    def __init__(self, uuid):
        self.uuid = uuid
        self.uuid_bytes = bytes.fromhex(uuid)

    async def handle_vless(self, websocket, first_msg):
        try:
            if len(first_msg) < 18 or first_msg[0] != 0: return False
            if first_msg[1:17] != self.uuid_bytes: return False
            i = first_msg[17] + 19
            if i + 3 > len(first_msg): return False
            port = struct.unpack('!H', first_msg[i:i+2])[0]; i += 2
            atyp = first_msg[i]; i += 1
            if atyp == 1: host = '.'.join(str(b) for b in first_msg[i:i+4]); i += 4
            elif atyp == 2:
                hl = first_msg[i]; i += 1
                host = first_msg[i:i+hl].decode(); i += hl
            elif atyp == 3:
                host = ':'.join(f'{(first_msg[j]<<8)+first_msg[j+1]:04x}' for j in range(i, i+16, 2)); i += 16
            else: return False
            if is_blocked_domain(host): await websocket.close(); return False
            await websocket.send_bytes(bytes([0, 0]))
            rh = await resolve_host(host)
            reader, writer = await asyncio.open_connection(rh, port)
            if i < len(first_msg): writer.write(first_msg[i:]); await writer.drain()
            async def fwd_ws():
                try:
                    async for msg in websocket:
                        if msg.type == aiohttp.WSMsgType.BINARY: writer.write(msg.data); await writer.drain()
                except: pass
                finally: writer.close(); await writer.wait_closed()
            async def fwd_tcp():
                try:
                    while True:
                        data = await reader.read(4096)
                        if not data: break
                        await websocket.send_bytes(data)
                except: pass
            await asyncio.gather(fwd_ws(), fwd_tcp())
            return True
        except: return False

    async def handle_trojan(self, websocket, first_msg):
        try:
            if len(first_msg) < 58: return False
            rh = first_msg[:56].decode('ascii', errors='ignore')
            h1 = hashlib.sha224(self.uuid.encode()).hexdigest()
            h2 = hashlib.sha224(UUID.encode()).hexdigest()
            if rh != h1 and rh != h2: return False
            offset = 58 if first_msg[56:58] == b'\r\n' else 56
            cmd = first_msg[offset]
            if cmd != 1: return False
            offset += 1
            atyp = first_msg[offset]; offset += 1
            if atyp == 1: host = '.'.join(str(b) for b in first_msg[offset:offset+4]); offset += 4
            elif atyp == 3:
                hl = first_msg[offset]; offset += 1
                host = first_msg[offset:offset+hl].decode(); offset += hl
            elif atyp == 4:
                host = ':'.join(f'{(first_msg[j]<<8)+first_msg[j+1]:04x}' for j in range(offset, offset+16, 2)); offset += 16
            else: return False
            port = struct.unpack('!H', first_msg[offset:offset+2])[0]; offset += 2
            if first_msg[offset:offset+2] == b'\r\n': offset += 2
            if is_blocked_domain(host): await websocket.close(); return False
            rh = await resolve_host(host)
            try:
                reader, writer = await asyncio.open_connection(rh, port)
                if offset < len(first_msg): writer.write(first_msg[offset:]); await writer.drain()
                async def fwd_ws():
                    try:
                        async for msg in websocket:
                            if msg.type == aiohttp.WSMsgType.BINARY: writer.write(msg.data); await writer.drain()
                    except: pass
                    finally: writer.close(); await writer.wait_closed()
                async def fwd_tcp():
                    try:
                        while True:
                            data = await reader.read(4096)
                            if not data: break
                            await websocket.send_bytes(data)
                    except: pass
                await asyncio.gather(fwd_ws(), fwd_tcp())
            except: pass
            return True
        except: return False

    async def handle_shadowsocks(self, websocket, first_msg):
        try:
            if len(first_msg) < 7: return False
            offset = 0
            atyp = first_msg[offset]; offset += 1
            if atyp == 1: host = '.'.join(str(b) for b in first_msg[offset:offset+4]); offset += 4
            elif atyp == 3:
                hl = first_msg[offset]; offset += 1
                host = first_msg[offset:offset+hl].decode(); offset += hl
            elif atyp == 4:
                host = ':'.join(f'{(first_msg[j]<<8)+first_msg[j+1]:04x}' for j in range(offset, offset+16, 2)); offset += 16
            else: return False
            port = struct.unpack('!H', first_msg[offset:offset+2])[0]; offset += 2
            if is_blocked_domain(host): await websocket.close(); return False
            rh = await resolve_host(host)
            try:
                reader, writer = await asyncio.open_connection(rh, port)
                if offset < len(first_msg): writer.write(first_msg[offset:]); await writer.drain()
                async def fwd_ws():
                    try:
                        async for msg in websocket:
                            if msg.type == aiohttp.WSMsgType.BINARY: writer.write(msg.data); await writer.drain()
                    except: pass
                    finally: writer.close(); await writer.wait_closed()
                async def fwd_tcp():
                    try:
                        while True:
                            data = await reader.read(4096)
                            if not data: break
                            await websocket.send_bytes(data)
                    except: pass
                await asyncio.gather(fwd_ws(), fwd_tcp())
            except: pass
            return True
        except: return False

# ── HTTP 路由 ──────────────────────────────────────────
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    path = request.path
    if f'/{WSPATH}' not in path: await ws.close(); return ws
    proxy = ProxyHandler(UUID.replace('-', ''))
    try:
        first_msg = await asyncio.wait_for(ws.receive(), timeout=5)
        if first_msg.type != aiohttp.WSMsgType.BINARY: await ws.close(); return ws
        msg_data = first_msg.data
        if len(msg_data) > 17 and msg_data[0] == 0:
            if await proxy.handle_vless(ws, msg_data): return ws
        if len(msg_data) >= 58:
            if await proxy.handle_trojan(ws, msg_data): return ws
        if len(msg_data) > 0 and msg_data[0] in (1, 3, 4):
            if await proxy.handle_shadowsocks(ws, msg_data): return ws
        await ws.close()
    except asyncio.TimeoutError: await ws.close()
    except: await ws.close()
    return ws

async def http_handler(request):
    try:
        with open('index.html') as f: return web.Response(text=f.read(), content_type='text/html')
    except: return web.Response(text='Hello world!', content_type='text/html')

# ── 主流程 ────────────────────────────────────────────
async def main():
    print('App running')
    os.makedirs(FILE_PATH, exist_ok=True)
    uf = os.path.join(FILE_PATH, 'uuid.txt')
    if not os.path.exists(uf): open(uf, 'w').write(UUID)

    actual_port = PORT
    if not is_port_available(actual_port):
        new_port = find_available_port(actual_port + 1)
        if new_port: actual_port = new_port
        else: logger.error('No available port'); sys.exit(1)

    if KOMARI_SERVER and KOMARI_TOKEN:
        threading.Timer(10, start_komari).start()
        threading.Thread(target=lambda: (time.sleep(15), komari_watchdog()), daemon=True).start()

    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get(f'/{WSPATH}', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', actual_port).start()
    logger.info(f'✅ server running on port {actual_port}')

    try:
        await get_isp()
        cd = CurrentDomain
        np = f'{NAME}-{ISP}' if NAME else ISP
        ss_mp = base64.b64encode(f'none:{UUID}'.encode()).decode()
        node_txt = '\n'.join([
            f'vless://{UUID}@{cd}:443?encryption=none&security=tls&sni={cd}&fp=chrome&type=ws&host={cd}&path=%2F{WSPATH}#{np}',
            f'trojan://{UUID}@{cd}:443?security=tls&sni={cd}&fp=chrome&type=ws&host={cd}&path=%2F{WSPATH}#{np}',
            f'ss://{ss_mp}@{cd}:443?plugin=v2ray-plugin;mode%3Dwebsocket;host%3D{cd};path%3D%2F{WSPATH};tls;sni%3D{cd};skip-cert-verify%3Dtrue;mux%3D0#{np}',
        ])
        await send_tg(f'✅ 节点已就绪 | {np}\n🌐 {cd}\n\n<pre>{base64.b64encode(node_txt.encode()).decode()}</pre>')
    except: pass

    try: await asyncio.Future()
    except: pass
    finally: await runner.cleanup()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print('\nServer stopped')