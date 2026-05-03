import requests
import time
import sys
import os
import logging
import configparser
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

# --- Config ---
def _load_server_url() -> str:
    exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    config_path = os.path.join(exe_dir, 'config.ini')
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
        log.info(f"Config loaded: {config_path}")
    url = cfg.get('agent', 'server_url', fallback=os.environ.get('NHSO_SERVER_URL', ''))
    if not url:
        log.error("server_url not set in config.ini — edit config.ini and restart")
        sys.exit(1)
    return url.rstrip('/')

def _load_client_id() -> str:
    import socket
    exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    config_path = os.path.join(exe_dir, 'config.ini')
    cfg = configparser.ConfigParser()
    if os.path.exists(config_path):
        cfg.read(config_path, encoding='utf-8')
    cid = cfg.get('agent', 'client_id', fallback=os.environ.get('NHSO_CLIENT_ID', '')).strip()
    if not cid:
        cid = socket.gethostname()
        log.info(f"client_id not set — using computer name: {cid}")
    return cid

SERVER_URL = _load_server_url()
CLIENT_ID = _load_client_id()
ENDPOINT = f"{SERVER_URL}/api/v1/kiosk/remote-insert"


class LocalCardAgent(CardObserver):
    def __init__(self):
        super().__init__()
        self.reader_index = 0
        log.info(f"NHSO Local Agent started. Targeting: {ENDPOINT}")
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

            log.info(f"Card read — CID: {cid}, Name: {name_th}")
            payload = {"cid": cid, "name_th": name_th}
            if CLIENT_ID:
                payload["client_id"] = CLIENT_ID
            response = requests.post(ENDPOINT, json=payload, timeout=60)

            if response.status_code == 200:
                log.info(f"Server response: {response.json()}")
            else:
                log.error(f"Server returned {response.status_code}: {response.text}")

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
