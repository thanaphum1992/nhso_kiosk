import requests
import time
import sys
import os
import logging
import configparser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from smartcard.System import readers
from smartcard.CardMonitoring import CardMonitor, CardObserver
from pythaiidcard.reader import ThaiIDCardReader as ThaiIDCardLib
from pythaiidcard.exceptions import ThaiIDCardException

# --- Logging ---
def _setup_logging():
    if getattr(sys, 'frozen', False):
        log_dir = os.path.join(os.environ.get('APPDATA', os.path.dirname(sys.executable)), 'NHSOLocalAgent')
    else:
        log_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(log_dir, exist_ok=True)
    handlers = [logging.FileHandler(os.path.join(log_dir, 'agent.log'), encoding='utf-8')]
    if sys.stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=handlers)

_setup_logging()
log = logging.getLogger(__name__)

def _mask_cid(cid: str) -> str:
    if not cid:
        return "-"
    digits = "".join(ch for ch in str(cid) if ch.isdigit())
    if len(digits) <= 4:
        return "****"
    return ("*" * (len(digits) - 4)) + digits[-4:]

def _mask_name(name: str) -> str:
    if not name:
        return "-"
    compact = " ".join(str(name).split())
    return (compact[:1] + "***") if compact else "-"

def _safe_server_summary(response: requests.Response) -> str:
    try:
        data = response.json()
        status = data.get("status", "unknown")
        visit = data.get("visit_number", "-")
        txn = data.get("transaction_id", "-")
        if txn and txn != "-":
            txn = "***" + str(txn)[-6:]
        return f"status={status}, visit={visit}, transaction={txn}"
    except Exception:
        return f"http_status={response.status_code}"

# --- Config ---
def _config_path() -> str:
    exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    return os.path.join(exe_dir, 'config.ini')

def _save_config(cfg: configparser.ConfigParser, config_path: str) -> None:
    with open(config_path, 'w', encoding='utf-8') as f:
        cfg.write(f)

def _load_server_url() -> str:
    config_path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
        log.info(f"Config loaded: {config_path}")
    else:
        log.warning(f"config.ini not found. Creating default config: {config_path}")

    if not cfg.has_section('agent'):
        cfg.add_section('agent')

    url = cfg.get('agent', 'server_url', fallback=os.environ.get('NHSO_SERVER_URL', 'http://localhost:8222')).strip()
    if not url:
        url = 'http://localhost:8222'

    cfg.set('agent', 'server_url', url)
    if not cfg.has_option('agent', 'client_id'):
        cfg.set('agent', 'client_id', '')
    if not cfg.has_option('agent', 'dep_code'):
        cfg.set('agent', 'dep_code', '')
    _save_config(cfg, config_path)

    if url == 'http://localhost:8222':
        log.warning("Using default server_url=http://localhost:8222. Edit config.ini if the server is on another computer.")

    return url.rstrip('/')

def _load_client_id() -> str:
    import socket
    config_path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
    cid = cfg.get('agent', 'client_id', fallback='').strip()
    if not cid:
        cid = socket.gethostname()
        # เขียนชื่อเครื่องลง config.ini อัตโนมัติ
        if not cfg.has_section('agent'):
            cfg.add_section('agent')
        cfg.set('agent', 'client_id', cid)
        _save_config(cfg, config_path)
        log.info(f"client_id auto-set to computer name: {cid}; saved to config.ini")
    else:
        log.info(f"client_id loaded from config: {cid}")
    return cid

def _load_dep_code() -> str:
    config_path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
    dep = cfg.get('agent', 'dep_code', fallback=os.environ.get('NHSO_DEP_CODE', '')).strip()
    if dep:
        log.info(f"dep_code set: {dep} — will filter visits by department")
    else:
        log.info("dep_code not set — will send all visits today")
    return dep

SERVER_URL = _load_server_url()
CLIENT_ID = _load_client_id()
DEP_CODE = _load_dep_code()
ENDPOINT = f"{SERVER_URL}/api/v1/kiosk/remote-insert"

# --- Local Shutdown Server ---
class _ShutdownHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == '/shutdown':
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b'OK')
            log.info("Shutdown requested by kiosk browser — exiting.")
            def _do_shutdown():
                import subprocess
                # ปิด Chrome/Edge kiosk
                subprocess.call('taskkill /F /IM chrome.exe /T >nul 2>&1', shell=True)
                subprocess.call('taskkill /F /IM msedge.exe /T >nul 2>&1', shell=True)
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=_do_shutdown, daemon=True).start()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Content-Type', 'text/plain')

    def log_message(self, format, *args):
        pass  # ปิด access log ของ HTTP server

def _start_shutdown_server(port: int = 8300):
    try:
        server = HTTPServer(('localhost', port), _ShutdownHandler)
        log.info(f"Shutdown server listening on localhost:{port}")
        server.serve_forever()
    except Exception as e:
        log.warning(f"Shutdown server failed to start: {e}")

threading.Thread(target=_start_shutdown_server, daemon=True).start()


class LocalCardAgent(CardObserver):
    def __init__(self):
        super().__init__()
        self.reader_index = 0
        log.info(f"NHSO Local Agent started. Targeting: {ENDPOINT} | client_id: {CLIENT_ID}")
        self._check_readers()

    def _check_readers(self):
        r = readers()
        if not r:
            log.warning("No card readers found. Please plug in a USB Smart Card reader.")
        else:
            log.info(f"Found readers: {r}")

    def _read_and_send(self):
        try:
            log.info("Reading card...")
            lib = ThaiIDCardLib(reader_index=self.reader_index, retry_count=3, skip_system_check=True)
            lib.connect()
            card = lib.read_card(include_photo=False)
            lib.disconnect()

            cid = card.cid
            t = card.thai_name
            name_th = f"{getattr(t,'prefix','')} {getattr(t,'first_name','')} {getattr(t,'last_name','')}".strip()

            log.info(f"Card read - CID: {_mask_cid(cid)}, Name: {_mask_name(name_th)}")
            payload = {"cid": cid, "name_th": name_th, "client_id": CLIENT_ID, "dep_code": DEP_CODE or None}
            response = requests.post(ENDPOINT, json=payload, timeout=60)

            if response.status_code == 200:
                log.info(f"Server response: {_safe_server_summary(response)}")
            else:
                log.error(f"Server returned HTTP {response.status_code}")

        except ThaiIDCardException as e:
            log.error(f"ThaiIDCard error: {e}")
        except requests.exceptions.ConnectionError:
            log.error(f"Cannot connect to server: {SERVER_URL}")
        except requests.exceptions.RequestException as e:
            log.error(f"Network error: {e}")
        except Exception as e:
            log.exception(f"Unexpected error: {e}")

    def update(self, observable, actions):
        (added_cards, removed_cards) = actions
        for _ in added_cards:
            log.info("Card inserted")
            time.sleep(0.5)
            self._read_and_send()
        for _ in removed_cards:
            log.info("Card removed")


if __name__ == "__main__":
    agent = LocalCardAgent()
    monitor = CardMonitor()
    monitor.addObserver(agent)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping agent...")
        monitor.deleteObserver(agent)
        sys.exit(0)
