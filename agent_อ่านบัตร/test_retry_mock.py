"""Mock test: POST retry while card present (no hardware)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_agent as la  # noqa: E402


def test_post_retry_while_card_present():
    agent = la.LocalCardAgent.__new__(la.LocalCardAgent)
    agent._card_present = False
    agent._send_ok = False
    agent._last_sent_pid = None
    agent._cached_card = {
        "pid": "1234567890123",
        "titleName": "นาย",
        "fname": "ทด",
        "lname": "สอบ",
    }
    agent._next_retry_at = 0.0
    agent._agent_warned = False
    def _resp(code: int):
        m = MagicMock()
        m.status_code = code
        if code == 200:
            m.json.return_value = {"status": "no_visit", "message_th": "test"}
        return m

    # 3 failures exhaust first _read_and_send; 4th call succeeds on retry
    side_effect = [_resp(503), _resp(503), _resp(503), _resp(200)]

    with patch.object(la, "_get_terminals", return_value=[{"isPresent": True}]), patch.object(
        la.requests, "post", side_effect=side_effect
    ) as mock_post:
        ok1 = agent._read_and_send()
        assert not ok1 and not agent._send_ok
        assert mock_post.call_count == 3

        agent._next_retry_at = 0
        ok2 = agent._read_and_send()
        assert ok2 and agent._send_ok
        assert mock_post.call_count == 4

    print("OK: POST retries until success without re-reading card")


def test_session_reset_on_remove():
    agent = la.LocalCardAgent.__new__(la.LocalCardAgent)
    agent._card_present = True
    agent._send_ok = True
    agent._last_sent_pid = "1234567890123"
    agent._cached_card = {"pid": "1234567890123"}
    agent._next_retry_at = 0.0
    agent._agent_warned = False

    with patch.object(la, "_get_terminals", return_value=[{"isPresent": False}]):
        agent.poll_once()

    assert not agent._send_ok
    assert agent._last_sent_pid is None
    assert agent._cached_card is None
    print("OK: session reset when card removed")


if __name__ == "__main__":
    test_post_retry_while_card_present()
    test_session_reset_on_remove()
    print("All mock tests passed")
