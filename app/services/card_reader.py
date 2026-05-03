import os
import asyncio
import time
import threading
import traceback
from typing import Optional
from smartcard.System import readers
from smartcard.CardMonitoring import CardMonitor, CardObserver
from pythaiidcard.reader import ThaiIDCardReader as ThaiIDCardLib
from pythaiidcard.exceptions import ThaiIDCardException
from app.services.card_mock import CardEvent
from app.core.logger import logger, mask_cid


class ThaiCardReader:
    def __init__(self):
        self.available = False
        self.reader_name = "none"
        self.monitoring = False
        self._reader_index = 0
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def connect(self):
        try:
            r = readers()
            if not r:
                logger.warning("[CardReader] No reader found")
                return False

            target_name = os.getenv("CARD_READER_NAME", "")
            for i, reader in enumerate(r):
                if not target_name or target_name in str(reader):
                    self._reader_index = i
                    self.reader_name = str(reader)
                    break

            logger.info(f"[CardReader] Connected: {self.reader_name} (index={self._reader_index})")
            self.available = True
            return True
        except Exception as e:
            logger.error(f"[CardReader] connect error: {e}\n{traceback.format_exc()}")
            self.available = False
            return False

    def _read_card(self) -> tuple[Optional[str], Optional[str]]:
        try:
            lib = ThaiIDCardLib(
                reader_index=self._reader_index,
                retry_count=3,
                skip_system_check=True,
            )
            lib.connect()
            card = lib.read_card(include_photo=False)
            lib.disconnect()

            cid = card.cid
            t = card.thai_name
            name_th = f"{getattr(t,'prefix','')} {getattr(t,'first_name','')} {getattr(t,'last_name','')}".strip() or "ผู้รับบริการ"
            logger.info(f"[CardReader] Card read OK — CID: {mask_cid(cid)} | Name: {name_th}")
            return cid, name_th
        except ThaiIDCardException as e:
            logger.error(f"[CardReader] ThaiIDCardException: {e}\n{traceback.format_exc()}")
            return None, None
        except Exception as e:
            logger.error(f"[CardReader] read error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            return None, None

    def start_monitor(self, event_queue, loop: asyncio.AbstractEventLoop):
        self._stop_event.clear()
        stop_event = self._stop_event
        reader_index = self._reader_index

        def monitor_thread():
            """
            สร้าง CardMonitor ใน regular thread เหมือน local_agent.py
            CardMonitor ต้องทำงานใน thread ปกติ ไม่ใช่ asyncio event loop
            """
            logger.info("[CardReader] Monitor thread starting")

            class ReaderObserver(CardObserver):
                def update(self, observable, actions):
                    added_cards, removed_cards = actions
                    logger.info(
                        f"[CardReader] observer.update added={len(added_cards)} removed={len(removed_cards)}"
                    )
                    for _ in added_cards:
                        logger.info("[CardReader] Card inserted — reading...")
                        time.sleep(0.5)
                        cid, name_th = None, None
                        try:
                            lib = ThaiIDCardLib(
                                reader_index=reader_index,
                                retry_count=3,
                                skip_system_check=True,
                            )
                            lib.connect()
                            card = lib.read_card(include_photo=False)
                            lib.disconnect()
                            cid = card.cid
                            t = card.thai_name
                            name_th = f"{getattr(t,'prefix','')} {getattr(t,'first_name','')} {getattr(t,'last_name','')}".strip() or "ผู้รับบริการ"
                            logger.info(f"[CardReader] Card OK — CID: {mask_cid(cid)}")
                        except ThaiIDCardException as e:
                            logger.error(f"[CardReader] ThaiIDCardException: {e}")
                        except Exception as e:
                            logger.error(f"[CardReader] read error: {type(e).__name__}: {e}\n{traceback.format_exc()}")

                        loop.call_soon_threadsafe(
                            event_queue.put_nowait,
                            CardEvent(type="insert", cid=cid, name_th=name_th),
                        )

                    for _ in removed_cards:
                        logger.info("[CardReader] Card removed")
                        loop.call_soon_threadsafe(
                            event_queue.put_nowait,
                            CardEvent(type="remove"),
                        )

            observer = ReaderObserver()
            monitor = CardMonitor()
            monitor.addObserver(observer)
            logger.info("[CardReader] CardMonitor started in dedicated thread")

            # Keep thread alive — same pattern as local_agent.py (no stop event)
            logger.info(f"[CardReader] stop_event.is_set()={stop_event.is_set()} before loop")
            while True:
                time.sleep(1)
                if stop_event.is_set():
                    logger.info("[CardReader] Stop event received — exiting")
                    break

            try:
                monitor.deleteObserver(observer)
            except Exception:
                pass
            logger.info("[CardReader] Monitor thread stopped")

        self._monitor_thread = threading.Thread(
            target=monitor_thread, daemon=True, name="CardMonitorThread"
        )
        self._monitor_thread.start()
        self.monitoring = True

    def stop_monitor(self):
        self._stop_event.set()
        self.monitoring = False

    def get_status(self) -> dict:
        return {
            "available": self.available,
            "reader_name": self.reader_name,
            "monitoring": self.monitoring,
        }
