import asyncio
from dataclasses import dataclass
from typing import Optional

@dataclass
class CardEvent:
    type: str        # "insert" | "remove"
    cid: Optional[str] = None
    name_th: Optional[str] = None
    result: Optional[dict] = None

class MockCardReader:
    def __init__(self):
        self.available = True
        self.reader_name = "Mock Reader"
        self._queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.monitoring = False

    def start_monitor(self, event_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self._queue = event_queue
        self._loop = loop
        self.monitoring = True

    def trigger_insert(self, cid: str, name_th: str = "ผู้ป่วยทดสอบ"):
        if self.monitoring and self._queue and self._loop:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, 
                CardEvent(type="insert", cid=cid, name_th=name_th)
            )

    def trigger_remove(self):
        if self.monitoring and self._queue and self._loop:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait, 
                CardEvent(type="remove")
            )

    def stop_monitor(self):
        self.monitoring = False

    def get_status(self) -> dict:
        return {
            "available": True, 
            "reader_name": self.reader_name,
            "monitoring": self.monitoring
        }

mock_reader = MockCardReader()
