#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""webapp - 纯 Python WebSocket 代理（VLESS/Trojan/SS）+ komari"""
import os, sys, socket, struct, hashlib, base64, asyncio, aiohttp, logging, ipaddress, subprocess, threading, re, time, platform, urllib.request, stat
from aiohttp import web
from pathlib import Path

# ── 从 .env 加载 ──────────────────────────────────────
_env = Path(__file__).parent / '.env'
if _env.exists():
    for l in _env.read_text().split('\n'):
        m = re.match(r'^\s*([^#=]+)=(.*)', l.strip())
        if m: os.environ.setdefault(m.group(1).strip(), m.group(2).strip().strip('"\''))

# ── 环境变量 ──────────────────────────────────────────
UUID = os.environ.get('UUID', '5959149a-fe2c-474a-a28d-fdf01e254cc4')
DOMAIN = os.environ.get('DOMAIN', '')
SUB_PATH = os.environ.get('SUB_PATH', 'sub')
NAME = os.environ.get('NAME', '')
WSPATH = os.environ.get('WSPATH', UUID[:8])
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', '').lower() == 'true'
DEBUG = os.environ.get('DEBUG', '').lower() == 'true'
CHAT_ID = os.environ.get('CHAT_ID', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
KOMARI_SERVER = os.environ.get('KOMARI_SERVER', '')
KOMARI_TOKEN = os.environ.get('KOMARI_TOKEN', '')
FILE_PATH = os.environ.get('FILE_PATH', '.cache')

# ── 日志 ──────────────────────────────────────────────
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s')
for name in ['aiohttp.access', 'aiohttp.server', 'aiohttp.client', 'aiohttp.internal', 'aiohttp.websocket']:
    logging.getLogger(name).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── 全局变量 ──────────────────────────────────────────
CurrentDomain = DOMAIN
CurrentPort = 443
Tls = 'tls'
ISP = ''
DNS_SERVERS = ['8.8.4.4', '1.1.1.1']
BLOCKED_DOMAINS = ['speedtest.net', 'fast.com', 'speedtest.cn', 'speed.cloudflare.com', 'speedof.me',
    'testmy.net', 'bandwidth.place', 'speed.io', 'librespeed.org', 'speedcheck.org']

# ── 工具 ──────────────────────────────────────────────
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

# ── 代理处理 ──────────────────────────────────────────
class ProxyHandler:
    def __init__(self, uuid):
        self.uuid = uuid
        self.uuid_bytes = bytes.fromhex(uuid)

    async def _forward(self, ws, writer, reader, first_data, offset):
        if offset < len(first_data):
            writer.write(first_data[offset:])
            await writer.drain()
        async def w2t():
            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.BINARY:
                        writer.write(msg.data); await writer.drain()
            except: pass
            finally:
                writer.close(); await writer.wait_closed()
        async def t2w():
            try:
                while True:
                    data = await reader.read(4096)
                    if not data: break
                    await ws.send_bytes(data)
            except: pass
        await asyncio.gather(w2t(), t2w())

    def _parse_addr(self, data, offset):
        atyp = data[offset]; offset += 1
        if atyp == 1:  # IPv4
            return '.'.join(str(b) for b in data[offset:offset+4]), offset + 4
        elif atyp == 2:  # 域名
            hl = data[offset]; offset += 1
            return data[offset:offset+hl].decode(), offset + hl
        elif atyp == 3:  # IPv6
            return ':'.join(f'{(data[j]<<8)+data[j+1]:04x}' for j in range(offset, offset+16, 2)), offset + 16
        return None, offset

    async def handle_vless(self, ws, msg):
        try:
            if len(msg) < 18 or msg[0] != 0 or msg[1:17] != self.uuid_bytes: return False
            i = msg[17] + 19
            if i + 3 > len(msg): return False
            port = struct.unpack('!H', msg[i:i+2])[0]; i += 2
            host, i = self._parse_addr(msg, i)
            if not host or is_blocked_domain(host): return False
            await ws.send_bytes(bytes([0, 0]))
            rh = await resolve_host(host)
            r, w = await asyncio.open_connection(rh, port)
            await self._forward(ws, w, r, msg, i)
            return True
        except: return False

    async def handle_trojan(self, ws, msg):
        try:
            if len(msg) < 58: return False
            rh = msg[:56].decode('ascii', errors='ignore')
            h1 = hashlib.sha224(self.uuid.encode()).hexdigest()
            h2 = hashlib.sha224(UUID.encode()).hexdigest()
            if rh != h1 and rh != h2: return False
            offset = 58 if msg[56:58] == b'\r\n' else 56
            if msg[offset] != 1: return False; offset += 1
            host, offset = self._parse_addr(msg, offset + 1)
            if not host: return False
            port = struct.unpack('!H', msg[offset:offset+2])[0]; offset += 2
            if msg[offset:offset+2] == b'\r\n': offset += 2
            if is_blocked_domain(host): return False
            rh = await resolve_host(host)
            r, w = await asyncio.open_connection(rh, port)
            await self._forward(ws, w, r, msg, offset)
            return True
        except: return False

    async def handle_shadowsocks(self, ws, msg):
        try:
            if len(msg) < 7: return False
            host, offset = self._parse_addr(msg, 0)
            if not host: return False
            port = struct.unpack('!H', msg[offset:offset+2])[0]; offset += 2
            if is_blocked_domain(host): return False
            rh = await resolve_host(host)
            r, w = await asyncio.open_connection(rh, port)
            await self._forward(ws, w, r, msg, offset)
            return True
        except: return False

# ── HTTP 路由 ──────────────────────────────────────────
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    if f'/{WSPATH}' not in request.path: await ws.close(); return ws
    proxy = ProxyHandler(UUID.replace('-', ''))
    try:
        fm = await asyncio.wait_for(ws.receive(), timeout=5)
        if fm.type != aiohttp.WSMsgType.BINARY: await ws.close(); return ws
        d = fm.data
        if len(d) > 17 and d[0] == 0 and await proxy.handle_vless(ws, d): return ws
        if len(d) >= 58 and await proxy.handle_trojan(ws, d): return ws
        if len(d) > 0 and d[0] in (1, 3, 4) and await proxy.handle_shadowsocks(ws, d): return ws
        await ws.close()
    except asyncio.TimeoutError: await ws.close()
    except: await ws.close()
    return ws

async def http_handler(request):
    if request.path == '/':
        try:
            with open('index.html') as f: return web.Response(text=f.read(), content_type='text/html')
        except: return web.Response(text='Hello world!', content_type='text/html')
    elif request.path == f'/{SUB_PATH}':
        await get_isp(); await get_ip()
        np = f"{NAME}-{ISP}" if NAME else ISP
        tp = 'tls' if Tls == 'tls' else 'none'
        stp = 'tls;' if Tls == 'tls' else ''
        v = f"vless://{UUID}@{CurrentDomain}:{CurrentPort}?encryption=none&security={tp}&sni={CurrentDomain}&fp=chrome&type=ws&host={CurrentDomain}&path=%2F{WSPATH}#{np}"
        t = f"trojan://{UUID}@{CurrentDomain}:{CurrentPort}?security={tp}&sni={CurrentDomain}&fp=chrome&type=ws&host={CurrentDomain}&path=%2F{WSPATH}#{np}"
        ss = base64.b64encode(f"none:{UUID}".encode()).decode()
        s = f"ss://{ss}@{CurrentDomain}:{CurrentPort}?plugin=v2ray-plugin;mode%3Dwebsocket;host%3D{CurrentDomain};path%3D%2F{WSPATH};{stp}sni%3D{CurrentDomain};skip-cert-verify%3Dtrue;mux%3D0#{np}"
        return web.Response(text=base64.b64encode(f'{v}\n{t}\n{s}'.encode()).decode() + '\n', content_type='text/plain')
    return web.Response(status=404, text='Not Found\n')

async def add_access_task():
    if not AUTO_ACCESS or not DOMAIN: return
    try:
        async with aiohttp.ClientSession() as s:
            await s.post("https://oooo.serv00.net/add-url", json={"url": f"https://{DOMAIN}/{SUB_PATH}"},
                headers={'Content-Type': 'application/json'})
        logger.info('Access task added')
    except: pass

# ── 主流程 ────────────────────────────────────────────
async def main():
    print('App running')
    actual_port = PORT
    if not is_port_available(actual_port):
        new_port = find_available_port(actual_port + 1)
        if new_port: actual_port = new_port
        else: logger.error('No available port'); sys.exit(1)

    # 启动 komari
    if KOMARI_SERVER and KOMARI_TOKEN:
        threading.Timer(10, start_komari).start()
        threading.Thread(target=lambda: (time.sleep(15), komari_watchdog()), daemon=True).start()

    # HTTP 服务
    app = web.Application()
    app.router.add_get('/', http_handler)
    app.router.add_get(f'/{SUB_PATH}', http_handler)
    app.router.add_get(f'/{WSPATH}', websocket_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', actual_port).start()
    logger.info(f'✅ server running on port {actual_port}')

    # TG 推送
    np = f'{NAME}-{ISP}' if NAME else ISP
    await send_tg(f'✅ 节点已就绪 | {np}\n🌐 {DOMAIN or CurrentDomain}\n\n订阅: /{SUB_PATH}')

    await add_access_task()
    try: await asyncio.Future()
    except: pass
    finally: await runner.cleanup()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print('\nServer stopped')