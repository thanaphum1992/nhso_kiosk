import requests
import time
import sys
import os
import logging
import configparser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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


def _load_config() -> dict:
    config_path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
        log.info(f"Config loaded: {config_path}")
    else:
        log.warning(f"config.ini not found. Creating default config: {config_path}")

    if not cfg.has_section('agent'):
        cfg.add_section('agent')

    defaults = {
        'server_url': os.environ.get('NHSO_SERVER_URL', 'http://localhost:8222'),
        'smartcard_agent_url': os.environ.get('NHSO_SMARTCARD_AGENT_URL', 'http://localhost:8189'),
        'client_id': '',
        'dep_code': '',
        'poll_interval_sec': '0.8',
        'card_settle_delay_sec': '1.5',
    }
    for key, default in defaults.items():
        if not cfg.has_option('agent', key):
            cfg.set('agent', key, default)

    server_url = cfg.get('agent', 'server_url', fallback='http://localhost:8222').strip() or 'http://localhost:8222'
    smartcard_url = cfg.get('agent', 'smartcard_agent_url', fallback='http://localhost:8189').strip() or 'http://localhost:8189'
    cfg.set('agent', 'server_url', server_url)
    cfg.set('agent', 'smartcard_agent_url', smartcard_url)
    _save_config(cfg, config_path)

    if server_url == 'http://localhost:8222':
        log.warning("Using default server_url=http://localhost:8222. Edit config.ini if the server is on another computer.")

    try:
        poll_interval = max(0.3, float(cfg.get('agent', 'poll_interval_sec', fallback='0.8')))
    except ValueError:
        poll_interval = 0.8
    try:
        settle_delay = max(0.0, float(cfg.get('agent', 'card_settle_delay_sec', fallback='1.5')))
    except ValueError:
        settle_delay = 1.5

    return {
        'server_url': server_url.rstrip('/'),
        'smartcard_url': smartcard_url.rstrip('/'),
        'poll_interval': poll_interval,
        'settle_delay': settle_delay,
        'cfg': cfg,
        'config_path': config_path,
    }


def _load_client_id(cfg: configparser.ConfigParser, config_path: str) -> str:
    import socket
    cid = cfg.get('agent', 'client_id', fallback='').strip()
    if not cid:
        cid = socket.gethostname()
        cfg.set('agent', 'client_id', cid)
        _save_config(cfg, config_path)
        log.info(f"client_id auto-set to computer name: {cid}; saved to config.ini")
    else:
        log.info(f"client_id loaded from config: {cid}")
    return cid


def _load_dep_code(cfg: configparser.ConfigParser) -> str:
    dep = cfg.get('agent', 'dep_code', fallback=os.environ.get('NHSO_DEP_CODE', '')).strip()
    if dep:
        log.info(f"dep_code set: {dep} — will filter visits by department")
    else:
        log.info("dep_code not set — will send all visits today")
    return dep


_CONFIG = _load_config()
SERVER_URL = _CONFIG['server_url']
SMARTCARD_URL = _CONFIG['smartcard_url']
POLL_INTERVAL = _CONFIG['poll_interval']
SETTLE_DELAY = _CONFIG['settle_delay']
CLIENT_ID = _load_client_id(_CONFIG['cfg'], _CONFIG['config_path'])
DEP_CODE = _load_dep_code(_CONFIG['cfg'])
ENDPOINT = f"{SERVER_URL}/api/v1/kiosk/remote-insert"

TERMINALS_URL = f"{SMARTCARD_URL}/api/smartcard/terminals"
READ_CARD_URL = f"{SMARTCARD_URL}/api/smartcard/read-card-only"


# --- Smart Card Agent (port 8189) ---
def _get_terminals(timeout: float = 5) -> list:
    response = requests.get(TERMINALS_URL, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def _any_card_present(terminals: list) -> bool:
    return any(bool(t.get('isPresent')) for t in terminals)


def _read_card_from_agent(timeout: float = 30) -> dict:
    response = requests.get(
        READ_CARD_URL,
        params={'readImageFlag': False},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"unexpected read response type: {type(data).__name__}")
    return data


def _cid_from_card(data: dict) -> str:
    return str(data.get('pid') or '').strip()


def _name_from_card(data: dict) -> str:
    parts = [data.get('titleName'), data.get('fname'), data.get('lname')]
    name = ' '.join(str(p).strip() for p in parts if p).strip()
    return name or 'ผู้รับบริการ'


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
        pass


def _start_shutdown_server(port: int = 8300):
    try:
        server = HTTPServer(('localhost', port), _ShutdownHandler)
        log.info(f"Shutdown server listening on localhost:{port}")
        server.serve_forever()
    except Exception as e:
        log.warning(f"Shutdown server failed to start: {e}")


threading.Thread(target=_start_shutdown_server, daemon=True).start()


class LocalCardAgent:
    RETRY_FAIL_SEC = 3.0
    MAX_READ_ATTEMPTS = 3
    MAX_POST_ATTEMPTS = 3

    def __init__(self):
        self._card_present = False
        self._send_ok = False
        self._last_sent_pid: str | None = None
        self._cached_card: dict | None = None
        self._next_retry_at = 0.0
        self._agent_warned = False
        log.info(
            f"NHSO Local Agent started (poll mode). "
            f"SmartCard: {SMARTCARD_URL} | Kiosk: {ENDPOINT} | client_id: {CLIENT_ID}"
        )
        self._check_smartcard_agent()

    def _check_smartcard_agent(self):
        try:
            terminals = _get_terminals()
            if not terminals:
                log.warning("Smart Card Agent: no terminals reported.")
            else:
                names = [t.get('terminalName', '?') for t in terminals]
                log.info(f"Smart Card Agent terminals: {names}")
        except requests.exceptions.ConnectionError:
            log.error(
                f"Cannot connect to Smart Card Agent at {SMARTCARD_URL}. "
                "Start the service on port 8189 before using the kiosk."
            )
        except Exception as e:
            log.warning(f"Smart Card Agent check failed: {e}")

    def _reset_card_session(self):
        self._send_ok = False
        self._last_sent_pid = None
        self._cached_card = None
        self._next_retry_at = 0.0

    def _read_card_data(self) -> dict | None:
        last_error = None
        for attempt in range(1, self.MAX_READ_ATTEMPTS + 1):
            try:
                log.info(f"Reading card via Smart Card Agent... (attempt {attempt}/{self.MAX_READ_ATTEMPTS})")
                data = _read_card_from_agent()
                cid = _cid_from_card(data)
                if not cid:
                    raise ValueError("empty pid from smartcard agent")
                self._cached_card = data
                return data
            except requests.exceptions.ConnectionError as e:
                last_error = e
                log.warning(f"Smart Card Agent unreachable (attempt {attempt}): {e}")
            except requests.exceptions.HTTPError as e:
                last_error = e
                log.warning(f"Smart Card Agent HTTP error (attempt {attempt}): {e}")
            except Exception as e:
                last_error = e
                log.warning(f"Read error (attempt {attempt}): {e}")
            if attempt < self.MAX_READ_ATTEMPTS:
                time.sleep(1.0)
        log.error(f"Card read failed after {self.MAX_READ_ATTEMPTS} attempts: {last_error}")
        self._cached_card = None
        return None

    def _post_to_server(self, cid: str, name_th: str) -> bool:
        payload = {
            'cid': cid,
            'name_th': name_th,
            'client_id': CLIENT_ID,
            'dep_code': DEP_CODE or None,
        }
        last_error = None
        for attempt in range(1, self.MAX_POST_ATTEMPTS + 1):
            try:
                log.info(f"Posting to kiosk server... (attempt {attempt}/{self.MAX_POST_ATTEMPTS})")
                response = requests.post(ENDPOINT, json=payload, timeout=60)
                if response.status_code == 200:
                    log.info(f"Server response: {_safe_server_summary(response)}")
                    return True
                log.warning(f"Server returned HTTP {response.status_code} (attempt {attempt})")
                last_error = f"HTTP {response.status_code}"
            except requests.exceptions.ConnectionError as e:
                last_error = e
                log.warning(f"Cannot connect to server (attempt {attempt}): {SERVER_URL} — {e}")
            except requests.exceptions.RequestException as e:
                last_error = e
                log.warning(f"Network error (attempt {attempt}): {e}")
            if attempt < self.MAX_POST_ATTEMPTS:
                time.sleep(1.0)
        log.error(f"POST failed after {self.MAX_POST_ATTEMPTS} attempts: {last_error}")
        return False

    def _read_and_send(self) -> bool:
        if self._send_ok and self._last_sent_pid:
            log.info("Already sent for current card — skip")
            return True

        data = self._cached_card
        if not data:
            data = self._read_card_data()
        if not data:
            self._send_ok = False
            return False

        cid = _cid_from_card(data)
        name_th = _name_from_card(data)
        log.info(f"Card read - CID: {_mask_cid(cid)}, Name: {_mask_name(name_th)}")

        if self._post_to_server(cid, name_th):
            self._send_ok = True
            self._last_sent_pid = cid
            self._cached_card = None
            return True

        self._send_ok = False
        self._next_retry_at = time.time() + self.RETRY_FAIL_SEC
        return False

    def _card_still_present(self) -> bool:
        try:
            return _any_card_present(_get_terminals())
        except Exception:
            return self._card_present

    def poll_once(self):
        try:
            present = _any_card_present(_get_terminals())
            self._agent_warned = False
        except requests.exceptions.ConnectionError:
            if not self._agent_warned:
                log.error(f"Cannot connect to Smart Card Agent: {SMARTCARD_URL}")
                self._agent_warned = True
            return
        except Exception as e:
            log.warning(f"Poll terminals failed: {e}")
            return

        was_present = self._card_present

        if present and not was_present:
            log.info("Card inserted (poll)")
            self._reset_card_session()
            if SETTLE_DELAY > 0:
                time.sleep(SETTLE_DELAY)
            if self._card_still_present():
                self._read_and_send()
            else:
                log.warning("Card removed during settle delay — waiting for re-insert")
        elif not present and was_present:
            log.info("Card removed")
            self._reset_card_session()
        elif present and was_present and not self._send_ok:
            if time.time() >= self._next_retry_at:
                self._read_and_send()

        self._card_present = present

    def run(self):
        log.info(f"Polling {TERMINALS_URL} every {POLL_INTERVAL}s")
        while True:
            self.poll_once()
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    agent = LocalCardAgent()
    try:
        agent.run()
    except KeyboardInterrupt:
        log.info("Stopping agent...")
        sys.exit(0)
