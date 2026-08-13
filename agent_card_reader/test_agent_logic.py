"""Verify local_agent has retry/session fixes (no hardware)."""
import sys
from pathlib import Path

SRC = (Path(__file__).resolve().parent / "local_agent.py").read_text(encoding="utf-8")
required = [
    "_send_ok",
    "_cached_card",
    "_reset_card_session",
    "_post_to_server",
    "_card_still_present",
    "RETRY_FAIL_SEC",
    "not self._send_ok",
]
missing = [s for s in required if s not in SRC]
print("=== Agent logic review ===")
if missing:
    for m in missing:
        print(f"FAIL: missing {m}")
    sys.exit(1)
print("OK: retry/session handling present")
sys.exit(0)
