"""One-shot test: read card from Smart Card Agent (:8189) and POST to kiosk remote-insert."""
import configparser
import json
import socket
import sys
import time
from pathlib import Path

import requests

AGENT_DIR = Path(__file__).resolve().parent
WAIT_CARD_SEC = 90
POLL_SEC = 0.8


def _load_urls() -> tuple[str, str]:
    smartcard = "http://localhost:8189"
    server = "http://localhost:8222"
    cfg_path = AGENT_DIR / "config.ini"
    if cfg_path.exists():
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path, encoding="utf-8")
        if cfg.has_section("agent"):
            smartcard = cfg.get("agent", "smartcard_agent_url", fallback=smartcard).strip() or smartcard
            server = cfg.get("agent", "server_url", fallback=server).strip() or server
    return smartcard.rstrip("/"), server.rstrip("/")


def _mask_cid(cid: str) -> str:
    digits = "".join(ch for ch in str(cid) if ch.isdigit())
    if len(digits) <= 4:
        return "****"
    return ("*" * (len(digits) - 4)) + digits[-4:]


def any_present(terminals: list) -> bool:
    return any(bool(t.get("isPresent")) for t in terminals)


def read_card(smartcard_url: str) -> dict:
    r = requests.get(
        f"{smartcard_url}/api/smartcard/read-card-only",
        params={"readImageFlag": False},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def name_th(data: dict) -> str:
    parts = [data.get("titleName"), data.get("fname"), data.get("lname")]
    return " ".join(str(p).strip() for p in parts if p).strip() or "ผู้รับบริการ"


def wait_for_card(smartcard_url: str) -> bool:
    print(f"Waiting for card (max {WAIT_CARD_SEC}s)... insert card now.")
    deadline = time.time() + WAIT_CARD_SEC
    while time.time() < deadline:
        try:
            t = requests.get(f"{smartcard_url}/api/smartcard/terminals", timeout=5).json()
            if any_present(t):
                print("Card detected.")
                time.sleep(1.5)
                return True
        except requests.RequestException as e:
            print(f"8189 error: {e}")
            return False
        time.sleep(POLL_SEC)
    return False


def main() -> int:
    smartcard_url, server_url = _load_urls()
    print(f"Smart Card Agent: {smartcard_url}")
    print(f"Kiosk server:     {server_url}/api/v1/kiosk/remote-insert")

    try:
        terminals = requests.get(f"{smartcard_url}/api/smartcard/terminals", timeout=5).json()
        print("Terminals:", json.dumps(terminals, ensure_ascii=False))
    except requests.RequestException as e:
        print(f"FAIL: cannot reach Smart Card Agent — {e}")
        return 1

    if not any_present(terminals):
        if not wait_for_card(smartcard_url):
            print("FAIL: no card inserted in time.")
            return 1

    try:
        data = read_card(smartcard_url)
    except requests.HTTPError as e:
        print(f"FAIL: read card — {e}")
        if e.response is not None:
            print(e.response.text[:500])
        return 1

    cid = str(data.get("pid") or "").strip()
    if not cid:
        print("FAIL: empty pid from smartcard agent")
        return 1

    payload = {
        "cid": cid,
        "name_th": name_th(data),
        "client_id": socket.gethostname(),
        "dep_code": None,
    }
    print(f"Read OK — CID: {_mask_cid(cid)}, name: {payload['name_th'][:1]}***")

    endpoint = f"{server_url}/api/v1/kiosk/remote-insert"
    for attempt in range(1, 4):
        try:
            resp = requests.post(endpoint, json=payload, timeout=60)
            print(f"POST status: {resp.status_code} (attempt {attempt})")
            try:
                print("Response:", json.dumps(resp.json(), ensure_ascii=False, indent=2))
            except Exception:
                print("Response text:", resp.text[:1000])
            return 0 if resp.status_code == 200 else 1
        except requests.ConnectionError:
            print(f"FAIL: cannot connect to kiosk server at {server_url} (attempt {attempt})")
            if attempt < 3:
                time.sleep(1)
    return 1


if __name__ == "__main__":
    sys.exit(main())
