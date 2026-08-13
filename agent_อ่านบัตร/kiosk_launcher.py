"""
Kiosk Launcher — opens browser + runs smart card polling agent.
Designed to be compiled into a single .exe via PyInstaller.
"""
import configparser
import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def resolve_config_path():
    """Resolve config.ini path — works both in dev and in compiled .exe."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent / "config.ini"
    return Path(__file__).resolve().parent / "config.ini"


def load_config():
    config_path = resolve_config_path()
    config = configparser.ConfigParser()

    server_url = "http://localhost:8222"
    smartcard_agent_url = "http://localhost:8189"
    client_id = ""
    dep_code = ""
    poll_interval_sec = 0.8
    card_settle_delay_sec = 1.5

    if config_path.is_file():
        config.read(str(config_path), encoding="utf-8")
        if config.has_section("agent"):
            server_url = config.get("agent", "server_url", fallback=server_url)
            smartcard_agent_url = config.get("agent", "smartcard_agent_url", fallback=smartcard_agent_url)
            client_id = config.get("agent", "client_id", fallback=client_id)
            dep_code = config.get("agent", "dep_code", fallback=dep_code)
            poll_interval_sec = config.getfloat("agent", "poll_interval_sec", fallback=poll_interval_sec)
            card_settle_delay_sec = config.getfloat("agent", "card_settle_delay_sec", fallback=card_settle_delay_sec)
    else:
        config["agent"] = {
            "server_url": server_url,
            "smartcard_agent_url": smartcard_agent_url,
            "client_id": client_id,
            "dep_code": dep_code,
            "poll_interval_sec": str(poll_interval_sec),
            "card_settle_delay_sec": str(card_settle_delay_sec),
        }
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)
        print(f"[INFO] Created config.ini at {config_path}")

    print(f"[INFO] Config loaded: {config_path}")

    if server_url == "http://localhost:8222":
        print("[WARNING] Using default server_url=http://localhost:8222. Edit config.ini if the server is on another computer.")

    if not client_id:
        client_id = os.environ.get("COMPUTERNAME", "kiosk-unknown")
        config["agent"]["client_id"] = client_id
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)
        print(f"[INFO] client_id auto-set to computer name: {client_id}; saved to config.ini")
    else:
        print(f"[INFO] client_id loaded from config: {client_id}")

    if dep_code:
        print(f"[INFO] dep_code from config: {dep_code}")
    else:
        print("[INFO] dep_code not set — will send all visits today")

    return {
        "server_url": server_url.rstrip("/"),
        "smartcard_agent_url": smartcard_agent_url.rstrip("/"),
        "client_id": client_id,
        "dep_code": dep_code,
        "poll_interval_sec": poll_interval_sec,
        "card_settle_delay_sec": card_settle_delay_sec,
    }


def launch_browser(server_url, client_id):
    """Open Chrome/Edge in kiosk-like mode pointing to the kiosk page."""
    kiosk_url = f"{server_url}/kiosk?client_id={client_id}"
    print(f"[INFO] Opening browser: {kiosk_url}")

    user_data_dir = os.path.join(os.environ.get("TEMP", "."), "chrome_kiosk_nhso")

    chrome_path = shutil.which("chrome")
    if not chrome_path:
        for p in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]:
            if os.path.isfile(p):
                chrome_path = p
                break

    if not chrome_path:
        edge_path = shutil.which("msedge")
        if not edge_path:
            for p in [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]:
                if os.path.isfile(p):
                    edge_path = p
                    break
        if edge_path:
            chrome_path = edge_path

    if chrome_path:
        try:
            subprocess.Popen([
                chrome_path,
                f"--app={kiosk_url}",
                f"--user-data-dir={user_data_dir}",
                "--kiosk",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--disable-session-crashed-bubble",
                "--disable-features=TranslateUI",
                "--disable-features=PasswordManagerEnabled",
            ])
            return
        except Exception as e:
            print(f"[WARNING] Failed to launch Chrome/Edge: {e}")

    print("[WARNING] Chrome/Edge not found, opening default browser")
    webbrowser.open(kiosk_url)


def run_agent(cfg):
    """Run the smart card polling agent (imported from local_agent)."""
    # Reuse the agent logic from local_agent.py
    import requests

    SMARTCARD_AGENT_URL = cfg["smartcard_agent_url"]
    KIOSK_SERVER_URL = f"{cfg['server_url']}/api/v1/kiosk/remote-insert"
    CLIENT_ID = cfg["client_id"]
    DEP_CODE = cfg["dep_code"]
    POLL_INTERVAL_SEC = cfg["poll_interval_sec"]
    CARD_SETTLE_DELAY_SEC = cfg["card_settle_delay_sec"]

    MAX_READ_ATTEMPTS = 3
    READ_RETRY_DELAY_SEC = 1.0
    MAX_POST_ATTEMPTS = 3
    POST_RETRY_DELAY_SEC = 1.0
    REQUEST_TIMEOUT_SEC = 10

    print(f"[INFO] NHSO Local Agent started (poll mode). SmartCard: {SMARTCARD_AGENT_URL} | Kiosk: {KIOSK_SERVER_URL} | client_id: {CLIENT_ID}")

    def wait_for_smartcard_agent(timeout=300):
        deadline = time.time() + timeout
        checked_once = False
        while time.time() < deadline:
            try:
                r = requests.get(f"{SMARTCARD_AGENT_URL}/api/smartcard/terminals", timeout=5)
                if r.status_code == 200:
                    if checked_once:
                        print("[INFO] Smart Card Agent is back online.")
                    return True
            except requests.RequestException:
                pass
            if not checked_once:
                print(f"[WARNING] Smart Card Agent not reachable at {SMARTCARD_AGENT_URL}. Retrying...")
                checked_once = True
            time.sleep(2)
        print(f"[ERROR] Smart Card Agent not reachable at {SMARTCARD_AGENT_URL} after {timeout}s — continuing anyway.")
        return False

    wait_for_smartcard_agent()

    try:
        resp = requests.get(f"{SMARTCARD_AGENT_URL}/api/smartcard/terminals", timeout=REQUEST_TIMEOUT_SEC)
        resp.raise_for_status()
        data = resp.json()
        terminals = data.get("terminals", []) if isinstance(data, dict) else data
        print(f"[INFO] Smart Card Agent terminals: {terminals}")
    except Exception as e:
        print(f"[WARNING] Could not enumerate terminals: {e}. Continuing...")

    print(f"[INFO] Polling {SMARTCARD_AGENT_URL}/api/smartcard/terminals every {POLL_INTERVAL_SEC}s")

    def _post_with_retry(payload):
        for attempt in range(1, MAX_POST_ATTEMPTS + 1):
            try:
                print(f"[INFO] Posting to kiosk server... (attempt {attempt}/{MAX_POST_ATTEMPTS})")
                r = requests.post(KIOSK_SERVER_URL, json=payload, timeout=REQUEST_TIMEOUT_SEC)
                try:
                    body = r.json()
                except Exception:
                    body = r.text
                print(f"[INFO] Server response: HTTP {r.status_code}, body={body}")
                if 200 <= r.status_code < 300:
                    return
                if 500 <= r.status_code < 600 and attempt < MAX_POST_ATTEMPTS:
                    print(f"[WARNING] Server error {r.status_code}, retrying in {POST_RETRY_DELAY_SEC}s...")
                    time.sleep(POST_RETRY_DELAY_SEC)
                    continue
                print(f"[ERROR] Server returned {r.status_code}, giving up on this card event.")
                return
            except requests.RequestException as e:
                print(f"[ERROR] POST failed: {e}")
                if attempt < MAX_POST_ATTEMPTS:
                    time.sleep(POST_RETRY_DELAY_SEC)
                else:
                    print("[ERROR] All POST attempts failed, giving up on this card event.")

    def _extract_cid_and_name(card_data):
        cid = card_data.get("cid") or card_data.get("national_id") or card_data.get("citizen_id")
        if not cid:
            for k, v in card_data.items():
                if isinstance(v, str) and len(v) == 13 and v.isdigit():
                    cid = v
                    break
        fname = (card_data.get("firstname") or card_data.get("first_name")
                 or card_data.get("fname") or card_data.get("name_th") or "").strip()
        lname = (card_data.get("lastname") or card_data.get("last_name")
                 or card_data.get("lname") or card_data.get("surname") or "").strip()
        name_th = f"{fname} {lname}".strip() if (fname or lname) else (card_data.get("name_th") or "")
        return cid, name_th

    last_card_state = "unknown"
    last_cid = None

    while True:
        try:
            resp = requests.get(f"{SMARTCARD_AGENT_URL}/api/smartcard/terminals", timeout=REQUEST_TIMEOUT_SEC)
            resp.raise_for_status()
            terminals_data = resp.json()
            if isinstance(terminals_data, dict):
                terminals_data = terminals_data.get("terminals", [])

            any_card_present = False
            for t in terminals_data:
                if isinstance(t, dict) and t.get("status") in ("card_present", "ready"):
                    any_card_present = True
                    break

            if any_card_present and last_card_state != "inserted":
                print("[INFO] Card inserted (poll)")
                time.sleep(CARD_SETTLE_DELAY_SEC)
                card_data = None
                for attempt in range(1, MAX_READ_ATTEMPTS + 1):
                    try:
                        print(f"[INFO] Reading card via Smart Card Agent... (attempt {attempt}/{MAX_READ_ATTEMPTS})")
                        r = requests.post(
                            f"{SMARTCARD_AGENT_URL}/api/smartcard/read",
                            json={"include_photo": False},
                            timeout=REQUEST_TIMEOUT_SEC,
                        )
                        if r.status_code == 200:
                            card_data = r.json()
                            break
                        else:
                            print(f"[WARNING] Read attempt {attempt} returned HTTP {r.status_code}: {r.text}")
                    except requests.RequestException as e:
                        print(f"[WARNING] Read attempt {attempt} failed: {e}")
                    if attempt < MAX_READ_ATTEMPTS:
                        time.sleep(READ_RETRY_DELAY_SEC)

                if card_data:
                    cid, name_th = _extract_cid_and_name(card_data)
                    if cid:
                        print(f"[INFO] Card read - CID: {cid[:3]}***{cid[-4:]}, Name: {name_th[:1]}***" if name_th else f"[INFO] Card read - CID: {cid[:3]}***{cid[-4:]}")
                        payload = {
                            "cid": cid,
                            "name_th": name_th,
                            "card_data": card_data,
                            "client_id": CLIENT_ID,
                            "dep_code": DEP_CODE,
                            "kiosk_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        _post_with_retry(payload)
                        last_cid = cid
                        last_card_state = "inserted"
                    else:
                        print(f"[ERROR] Could not extract CID from card data: {card_data}")
                        last_card_state = "inserted"
                else:
                    print("[ERROR] Failed to read card after all retries.")
                    last_card_state = "inserted"

            elif not any_card_present and last_card_state != "removed":
                print("[INFO] Card removed")
                last_cid = None
                last_card_state = "removed"

        except requests.RequestException as e:
            print(f"[ERROR] Polling error: {e}")

        time.sleep(POLL_INTERVAL_SEC)


def main():
    # Force unbuffered output (important when compiled as .exe)
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

    # Set console title
    ctypes.windll.kernel32.SetConsoleTitleW("NHSO Kiosk Agent")

    print("=" * 50)
    print("  NHSO Kiosk Agent — Smart Card Reader")
    print("=" * 50)

    cfg = load_config()

    # Launch browser in a separate thread so agent polling starts immediately
    browser_thread = threading.Thread(target=launch_browser, args=(cfg["server_url"], cfg["client_id"]), daemon=True)
    browser_thread.start()

    # Small delay to let browser start before agent begins polling
    time.sleep(1)

    # Run the agent (blocks forever)
    run_agent(cfg)


if __name__ == "__main__":
    main()
