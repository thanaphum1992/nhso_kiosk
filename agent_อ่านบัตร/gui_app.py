"""
NHSO Kiosk Agent — Desktop GUI Application
tkinter-based config editor, status monitor, log viewer, and smart card polling agent.
"""
import configparser
import io
import os
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

# Force unbuffered output for .exe (only if stdout/stderr exist)
if getattr(sys, 'frozen', False):
    if sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, line_buffering=True)
    if sys.stderr is not None:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, line_buffering=True)

import requests


# ---------------------------------------------------------------------------
# Single Instance Protection (ป้องกันเปิดซ้ำ)
# ---------------------------------------------------------------------------
def check_single_instance():
    """ตรวจสอบว่ามี instance อื่นรันอยู่หรือไม่ ใช้ Windows Mutex"""
    try:
        import ctypes
        mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "NHSO_Kiosk_Agent_Single_Instance")
        last_error = ctypes.windll.kernel32.GetLastError()
        
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            # มี instance อื่นรันอยู่แล้ว
            ctypes.windll.kernel32.CloseHandle(mutex)
            return None
        else:
            # คืนค่า mutex handle เพื่อไม่ให้ถูก garbage collected
            return mutex
    except Exception as e:
        print(f"Warning: Mutex check failed: {e}")
        return "fallback"  # อนุญาตให้รันต่อถ้า mutex check ล้มเหลว


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
def _config_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.ini')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')


DEFAULTS = {
    'server_url': 'http://localhost:8222',
    'smartcard_agent_url': 'http://localhost:8189',
    'client_id': '',
    'dep_code': '',
    'poll_interval_sec': '0.8',
    'card_settle_delay_sec': '1.5',
}


def load_config() -> dict:
    path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path, encoding='utf-8')
    if not cfg.has_section('agent'):
        cfg.add_section('agent')
    for key, default in DEFAULTS.items():
        if not cfg.has_option('agent', key):
            cfg.set('agent', key, default)
    with open(path, 'w', encoding='utf-8') as f:
        cfg.write(f)
    return {
        'server_url': (cfg.get('agent', 'server_url', fallback=DEFAULTS['server_url']).strip() or DEFAULTS['server_url']),
        'smartcard_agent_url': (cfg.get('agent', 'smartcard_agent_url', fallback=DEFAULTS['smartcard_agent_url']).strip() or DEFAULTS['smartcard_agent_url']),
        'client_id': cfg.get('agent', 'client_id', fallback='').strip(),
        'dep_code': cfg.get('agent', 'dep_code', fallback='').strip(),
        'poll_interval_sec': float(cfg.get('agent', 'poll_interval_sec', fallback='0.8') or '0.8'),
        'card_settle_delay_sec': float(cfg.get('agent', 'card_settle_delay_sec', fallback='1.5') or '1.5'),
    }


def save_config(values: dict) -> None:
    path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path, encoding='utf-8')
    if not cfg.has_section('agent'):
        cfg.add_section('agent')
    for key, val in values.items():
        cfg.set('agent', key, str(val))
    with open(path, 'w', encoding='utf-8') as f:
        cfg.write(f)


# ---------------------------------------------------------------------------
# Browser launcher (from kiosk_launcher.py)
# ---------------------------------------------------------------------------
def launch_browser(server_url: str, client_id: str):
    kiosk_url = f"{server_url.rstrip('/')}/kiosk?client_id={client_id}"
    import webbrowser
    webbrowser.open(kiosk_url)
    return f'เปิด browser: {kiosk_url}'


# ---------------------------------------------------------------------------
# Agent polling (runs in background thread)
# ---------------------------------------------------------------------------
class AgentWorker(threading.Thread):
    def __init__(self, config: dict, log_queue: queue.Queue, status_queue: queue.Queue):
        super().__init__(daemon=True)
        self.config = config
        self.log_q = log_queue
        self.status_q = status_queue
        self._stop_event = threading.Event()
        self.cards_processed = 0
        self.start_time = None

    def _log(self, level: str, msg: str):
        self.log_q.put((level, msg))

    def _status(self, key: str, value):
        self.status_q.put((key, value))

    def stop(self):
        self._stop_event.set()

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        self.start_time = time.time()
        cfg = self.config
        SCARD_URL = cfg['smartcard_agent_url'].rstrip('/')
        KIOSK_URL = f"{cfg['server_url'].rstrip('/')}/api/v1/kiosk/remote-insert"
        CLIENT_ID = cfg['client_id'] or socket.gethostname()
        DEP_CODE = cfg['dep_code']
        try:
            POLL_SEC = float(cfg['poll_interval_sec'])
        except (ValueError, TypeError):
            POLL_SEC = 0.8
        try:
            SETTLE_SEC = float(cfg['card_settle_delay_sec'])
        except (ValueError, TypeError):
            SETTLE_SEC = 1.5

        self._log('INFO', f'Agent เริ่มทำงาน — SmartCard: {SCARD_URL} | Server: {KIOSK_URL}')
        self._log('INFO', f'client_id: {CLIENT_ID} | dep_code: {DEP_CODE or "(ทั้งหมด)"}')
        self._status('agent_state', 'running')

        # Wait for Smart Card Agent
        self._log('INFO', 'รอ Smart Card Agent...')
        for _ in range(60):
            if self.stopped:
                self._status('agent_state', 'stopped')
                return
            try:
                r = requests.get(f'{SCARD_URL}/api/smartcard/terminals', timeout=3)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2)

        try:
            resp = requests.get(f'{SCARD_URL}/api/smartcard/terminals', timeout=5)
            resp.raise_for_status()
            data = resp.json()
            terminals = data if isinstance(data, list) else data.get('terminals', [])
            names = [t.get('terminalName', t.get('name', '?')) if isinstance(t, dict) else str(t) for t in terminals]
            self._log('INFO', f'เครื่องอ่านบัตร: {names}')
            self._status('reader_name', ', '.join(names) if names else 'ไม่พบ')
            self._status('smartcard_agent', 'connected')
        except Exception as e:
            self._log('WARNING', f'ไม่สามารถตรวจเครื่องอ่านบัตร: {e}')
            self._status('smartcard_agent', 'error')
            self._status('reader_name', 'ไม่ทราบ')

        self._log('INFO', f'เริ่ม polling ทุก {POLL_SEC} วินาที')
        card_present = False
        last_sent_cid = None  # ป้องกันการส่ง CID เดิมซ้ำ
        poll_count = 0

        while not self.stopped:
            poll_count += 1
            
            try:
                resp = requests.get(f'{SCARD_URL}/api/smartcard/terminals', timeout=5)
                resp.raise_for_status()
                data = resp.json()
                terminals = data if isinstance(data, list) else data.get('terminals', [])
                self._status('smartcard_agent', 'connected')

                # Check card presence (same logic as local_agent.py)
                present = any(bool(t.get('isPresent')) for t in terminals if isinstance(t, dict))
                self._status('card_present', present)

                if present and not card_present:
                    # Card just inserted
                    self._log('INFO', f'📥 พบบัตร (poll #{poll_count}) — กำลังอ่าน...')
                    time.sleep(SETTLE_SEC)

                    # Verify card still present
                    try:
                        resp2 = requests.get(f'{SCARD_URL}/api/smartcard/terminals', timeout=5)
                        still_present = any(bool(t.get('isPresent')) for t in resp2.json() if isinstance(t, dict))
                    except:
                        still_present = present

                    if still_present:
                        # Read card data
                        card_data = None
                        for attempt in range(1, 4):
                            try:
                                r = requests.get(
                                    f'{SCARD_URL}/api/smartcard/read-card-only',
                                    params={'readImageFlag': False},
                                    timeout=30,
                                )
                                r.raise_for_status()
                                card_data = r.json()
                                if not isinstance(card_data, dict):
                                    raise ValueError(f'unexpected response type: {type(card_data).__name__}')
                                break
                            except Exception as e:
                                self._log('WARNING', f'อ่านบัตร attempt {attempt}: {e}')
                                if attempt < 3:
                                    time.sleep(1)

                        if card_data:
                            # Extract CID and name (same as local_agent.py)
                            cid = str(card_data.get('pid') or '').strip()
                            parts = [card_data.get('titleName'), card_data.get('fname'), card_data.get('lname')]
                            name_th = ' '.join(str(p).strip() for p in parts if p).strip() or 'ผู้รับบริการ'

                            if cid:
                                # ตรวจสอบว่าเคยส่ง CID นี้ไปแล้วหรือยัง
                                if cid == last_sent_cid:
                                    self._log('INFO', f'⏭️ CID เดิม ({cid[-4:]}) — ข้ามการส่งซ้ำ')
                                    card_present = present
                                    continue
                                
                                masked = ('*' * (len(cid) - 4)) + cid[-4:] if len(cid) > 4 else cid
                                name_mask = (name_th[:1] + '***') if name_th else '-'
                                self._log('INFO', f'✅ อ่านบัตรสำเร็จ — CID: {masked}, ชื่อ: {name_mask}')
                                self._status('last_card', f'{name_mask} ({time.strftime("%H:%M:%S")})')

                                payload = {
                                    'cid': cid,
                                    'name_th': name_th,
                                    'client_id': CLIENT_ID,
                                    'dep_code': DEP_CODE or None,
                                }
                                # POST with retry
                                post_success = False
                                for attempt in range(1, 4):
                                    try:
                                        r = requests.post(KIOSK_URL, json=payload, timeout=60)
                                        if r.status_code == 200:
                                            try:
                                                body = r.json()
                                                s = body.get('status', '?')
                                                v = body.get('visit_number', '-')
                                                self._log('INFO', f'📤 Server: status={s}, visit={v}')
                                                self._status('last_server', f'status={s}, visit={v} ({time.strftime("%H:%M:%S")})')
                                            except:
                                                self._log('INFO', f'📤 Server: HTTP {r.status_code}')
                                                self._status('last_server', f'HTTP {r.status_code} ({time.strftime("%H:%M:%S")})')
                                            self.cards_processed += 1
                                            self._status('cards_processed', self.cards_processed)
                                            post_success = True
                                            break
                                        else:
                                            self._log('WARNING', f'Server returned HTTP {r.status_code} (attempt {attempt})')
                                            if attempt < 3:
                                                time.sleep(1)
                                    except Exception as e:
                                        self._log('ERROR', f'POST failed (attempt {attempt}): {e}')
                                        if attempt < 3:
                                            time.sleep(1)
                                
                                # ถ้า POST สำเร็จ ให้จำ CID ไว้เพื่อป้องกันการส่งซ้ำ
                                if post_success:
                                    last_sent_cid = cid
                            else:
                                self._log('WARNING', f'ไม่พบ CID ในข้อมูลบัตร')
                        else:
                            self._log('ERROR', 'อ่านบัตรไม่สำเร็จหลัง 3 ครั้ง')

                elif not present and card_present:
                    # Card just removed
                    self._log('INFO', '📤 ถอดบัตรแล้ว')
                    last_sent_cid = None  # reset เมื่อถอดบัตร

                card_present = present

            except requests.RequestException as e:
                self._status('smartcard_agent', 'disconnected')
                self._log('ERROR', f'เชื่อมต่อ Smart Card Agent ไม่ได้: {e}')

            # Sleep in small chunks so we can stop quickly
            for _ in range(int(POLL_SEC * 10)):
                if self.stopped:
                    break
                time.sleep(0.1)

        self._status('agent_state', 'stopped')
        self._log('INFO', 'Agent หยุดทำงานแล้ว')


# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------
def _create_tray_icon_image():
    """Create a simple icon using Pillow."""
    from PIL import Image, ImageDraw
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=(0, 120, 215))
    draw.text((18, 16), 'NH', fill='white')
    return img


# ---------------------------------------------------------------------------
# Main GUI Application
# ---------------------------------------------------------------------------
class NHSOKioskApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('NHSO Kiosk Agent')
        self.root.geometry('680x520')
        self.root.minsize(600, 460)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self.config = load_config()
        self.log_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.agent_worker = None
        self.tray_icon = None
        self.status_updater_id = None

        self._build_ui()
        self._setup_copy_paste_shortcuts()
        self._load_settings_into_form()
        self._start_status_polling()
        self._process_log_queue()
        self._process_status_queue()

    def _setup_copy_paste_shortcuts(self):
        """Add keyboard shortcuts and context menu for all entry widgets"""
        # Bind global keyboard shortcuts
        self.root.bind_all('<Control-c>', self._copy_event)
        self.root.bind_all('<Control-x>', self._cut_event)
        self.root.bind_all('<Control-v>', self._paste_event)
        self.root.bind_all('<Control-a>', self._select_all_event)
        
        # Create context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._cut_event)
        self.context_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._copy_event)
        self.context_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self._paste_event)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self._select_all_event)
        
        # Bind right-click to all entry and text widgets
        self.root.bind_class('Entry', '<Button-3>', self._show_context_menu)
        self.root.bind_class('Text', '<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        """Show context menu on right-click"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _copy_event(self, event=None):
        """Handle Ctrl+C"""
        try:
            widget = self.root.focus_get()
            if widget and isinstance(widget, (tk.Entry, tk.Text, scrolledtext.ScrolledText)):
                widget.event_generate('<<Copy>>')
        except:
            pass
        return 'break'

    def _cut_event(self, event=None):
        """Handle Ctrl+X"""
        try:
            widget = self.root.focus_get()
            if widget and isinstance(widget, (tk.Entry, tk.Text, scrolledtext.ScrolledText)):
                widget.event_generate('<<Cut>>')
        except:
            pass
        return 'break'

    def _paste_event(self, event=None):
        """Handle Ctrl+V"""
        try:
            widget = self.root.focus_get()
            if widget and isinstance(widget, (tk.Entry, tk.Text, scrolledtext.ScrolledText)):
                widget.event_generate('<<Paste>>')
        except:
            pass
        return 'break'

    def _select_all_event(self, event=None):
        """Handle Ctrl+A"""
        try:
            widget = self.root.focus_get()
            if widget and isinstance(widget, (tk.Entry, tk.Text, scrolledtext.ScrolledText)):
                widget.select_range(0, 'end')
                widget.icursor('end')
        except:
            pass
        return 'break'

    def _build_ui(self):
        style = ttk.Style()
        style.configure('Green.TLabel', foreground='green')
        style.configure('Red.TLabel', foreground='red')
        style.configure('Orange.TLabel', foreground='orange')
        style.configure('Status.TLabel', font=('Segoe UI', 10))

        # --- Top status bar ---
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill='x')

        ttk.Label(top, text='NHSO Kiosk Agent', font=('Segoe UI', 14, 'bold')).pack(side='left')

        self.lbl_agent_status = ttk.Label(top, text='● หยุดอยู่', style='Red.TLabel')
        self.lbl_agent_status.pack(side='right', padx=8)

        self.lbl_sc_status = ttk.Label(top, text='● Smart Card: ตรวจ...', style='Orange.TLabel')
        self.lbl_sc_status.pack(side='right', padx=8)

        # --- Notebook (tabs) ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=8, pady=(0, 4))

        self._build_settings_tab()
        self._build_status_tab()
        self._build_log_tab()

        # --- Bottom buttons ---
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill='x')

        self.btn_start = ttk.Button(bottom, text='▶ เริ่มอ่านบัตร', command=self._start_agent)
        self.btn_start.pack(side='left', padx=4)

        self.btn_stop = ttk.Button(bottom, text='⏹ หยุด', command=self._stop_agent, state='disabled')
        self.btn_stop.pack(side='left', padx=4)

        self.btn_browser = ttk.Button(bottom, text='🌐 เปิด Kiosk Browser', command=self._open_browser)
        self.btn_browser.pack(side='left', padx=4)

        self.lbl_uptime = ttk.Label(bottom, text='Uptime: -')
        self.lbl_uptime.pack(side='right', padx=4)

    def _build_settings_tab(self):
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text=' ⚙ ตั้งค่า ')

        self.settings_vars = {}
        fields = [
            ('server_url', 'Server URL (kiosk):', 'http://localhost:8222'),
            ('smartcard_agent_url', 'Smart Card Agent URL:', 'http://localhost:8189'),
            ('client_id', 'Client ID (ชื่อเครื่อง):', '(เว้นว่าง = ใช้ COMPUTERNAME)'),
            ('dep_code', 'Dep Code (รหัสแผนก):', '(เว้นว่าง = ทุกแผนก)'),
            ('poll_interval_sec', 'Poll Interval (วินาที):', '0.8'),
            ('card_settle_delay_sec', 'Settle Delay (วินาที):', '1.5'),
        ]

        for i, (key, label, hint) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky='w', pady=4)
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky='ew', padx=8, pady=4)
            ttk.Label(frame, text=hint, foreground='gray').grid(row=i, column=2, sticky='w', pady=4)
            self.settings_vars[key] = var

        frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=3, pady=16)
        ttk.Button(btn_frame, text='💾 บันทึกค่า', command=self._save_settings).pack(side='left', padx=4)
        ttk.Button(btn_frame, text='🔄 โหลดใหม่', command=self._load_settings_into_form).pack(side='left', padx=4)

    def _build_status_tab(self):
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text=' 📊 สถานะ ')

        self.status_labels = {}
        rows = [
            ('smartcard_agent', 'Smart Card Agent (port 8189):'),
            ('reader_name', 'เครื่องอ่านบัตร:'),
            ('card_present', 'สถานะบัตร:'),
            ('agent_state', 'Agent:'),
            ('last_card', 'บัตรล่าสุด:'),
            ('last_server', 'Server ตอบล่าสุด:'),
            ('cards_processed', 'จำนวนบัตรที่ส่งแล้ว:'),
        ]

        for i, (key, label) in enumerate(rows):
            ttk.Label(frame, text=label, font=('Segoe UI', 10, 'bold')).grid(row=i, column=0, sticky='w', pady=6)
            lbl = ttk.Label(frame, text='—', font=('Segoe UI', 10))
            lbl.grid(row=i, column=1, sticky='w', padx=12, pady=6)
            self.status_labels[key] = lbl

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(rows), column=0, columnspan=2, pady=16)
        ttk.Button(btn_frame, text='🔍 ตรวจสถานะตอนนี้', command=self._check_smartcard_status).pack(side='left', padx=4)

    def _build_log_tab(self):
        frame = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(frame, text=' 📋 Log ')

        self.log_text = scrolledtext.ScrolledText(frame, height=15, state='normal',
                                                  font=('Consolas', 9), wrap='word')
        self.log_text.pack(fill='both', expand=True)
        
        # Prevent editing but allow selection and copying
        self.log_text.bind('<Key>', lambda e: 'break')
        self.log_text.bind('<BackSpace>', lambda e: 'break')
        self.log_text.bind('<Delete>', lambda e: 'break')

        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', pady=4)
        self.auto_scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text='Auto-scroll', variable=self.auto_scroll_var).pack(side='left')
        ttk.Button(bottom, text='📋 Copy All', command=self._copy_all_log).pack(side='right', padx=2)
        ttk.Button(bottom, text='📋 Copy Selected', command=self._copy_selected_log).pack(side='right', padx=2)
        ttk.Button(bottom, text='🗑 ล้าง Log', command=self._clear_log).pack(side='right', padx=2)

    # --- Settings ---
    def _load_settings_into_form(self):
        self.config = load_config()
        for key, var in self.settings_vars.items():
            var.set(self.config.get(key, ''))

    def _save_settings(self):
        values = {}
        for key, var in self.settings_vars.items():
            values[key] = var.get().strip()
        if not values['client_id']:
            values['client_id'] = socket.gethostname()
        save_config(values)
        self.config = load_config()
        self._log_to_gui('INFO', f'💾 บันทึก config.ini สำเร็จ — {_config_path()}')
        if self.agent_worker and not self.agent_worker.stopped:
            self._log_to_gui('WARNING', '⚠ Agent กำลังทำงานอยู่ — การตั้งค่าใหม่จะมีผลหลังหยุดแล้วเริ่มใหม่')

    # --- Agent ---
    def _start_agent(self):
        if self.agent_worker and not self.agent_worker.stopped:
            return
        self.config = load_config()
        for key, var in self.settings_vars.items():
            self.config[key] = var.get().strip() or self.config.get(key, '')
        if not self.config['client_id']:
            self.config['client_id'] = socket.gethostname()

        self.agent_worker = AgentWorker(self.config, self.log_queue, self.status_queue)
        self.agent_worker.start()

        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self._log_to_gui('INFO', '▶ เริ่ม Agent อ่านบัตร')

    def _stop_agent(self):
        if self.agent_worker:
            self.agent_worker.stop()
            self.btn_start.config(state='normal')
            self.btn_stop.config(state='disabled')
            self._log_to_gui('INFO', '⏹ กำลังหยุด Agent...')

    def _open_browser(self):
        server_url = self.settings_vars['server_url'].get().strip() or 'http://localhost:8222'
        client_id = self.settings_vars['client_id'].get().strip() or socket.gethostname()
        result = launch_browser(server_url, client_id)
        self._log_to_gui('INFO', f'🌐 {result}')

    # --- Status polling ---
    def _start_status_polling(self):
        self._check_smartcard_status()
        self.status_updater_id = self.root.after(5000, self._start_status_polling)

    def _check_smartcard_status(self):
        def _check():
            url = self.settings_vars['smartcard_agent_url'].get().strip() or 'http://localhost:8189'
            try:
                r = requests.get(f'{url.rstrip("/")}/api/smartcard/terminals', timeout=3)
                data = r.json()
                terminals = data if isinstance(data, list) else data.get('terminals', [])
                names = [t.get('terminalName', t.get('name', '?')) if isinstance(t, dict) else str(t) for t in terminals]
                any_present = any(
                    (t.get('isPresent') or t.get('status') in ('card_present', 'ready'))
                    for t in terminals if isinstance(t, dict)
                )
                self.root.after(0, self._update_sc_status, 'connected', names, any_present)
            except Exception:
                self.root.after(0, self._update_sc_status, 'disconnected', [], False)

        threading.Thread(target=_check, daemon=True).start()

    def _update_sc_status(self, state, readers, card_present):
        if state == 'connected':
            self.lbl_sc_status.config(text='● Smart Card: เชื่อมต่อแล้ว', style='Green.TLabel')
            self.status_labels['smartcard_agent'].config(text='✅ เชื่อมต่อแล้ว', foreground='green')
            self.status_labels['reader_name'].config(text=', '.join(readers) if readers else 'ไม่พบ')
            self.status_labels['card_present'].config(
                text='📥 มีบัตรเสียบอยู่' if card_present else '📤 ไม่มีบัตร',
                foreground='blue' if card_present else 'gray',
            )
        else:
            self.lbl_sc_status.config(text='● Smart Card: ขาดการเชื่อมต่อ', style='Red.TLabel')
            self.status_labels['smartcard_agent'].config(text='❌ ไม่สามารถเชื่อมต่อได้', foreground='red')
            self.status_labels['reader_name'].config(text='—')
            self.status_labels['card_present'].config(text='—', foreground='gray')

    # --- Log / Status queue processing ---
    def _process_log_queue(self):
        while True:
            try:
                level, msg = self.log_queue.get_nowait()
                self._log_to_gui(level, msg)
            except queue.Empty:
                break
        self.root.after(200, self._process_log_queue)

    def _process_status_queue(self):
        while True:
            try:
                key, value = self.status_queue.get_nowait()
                self._update_status_label(key, value)
            except queue.Empty:
                break
        # Update uptime
        if self.agent_worker and self.agent_worker.start_time and not self.agent_worker.stopped:
            elapsed = int(time.time() - self.agent_worker.start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.lbl_uptime.config(text=f'Uptime: {h:02d}:{m:02d}:{s:02d}')
        else:
            self.lbl_uptime.config(text='Uptime: -')

        self.root.after(300, self._process_status_queue)

    def _update_status_label(self, key, value):
        lbl = self.status_labels.get(key)
        if not lbl:
            return
        if key == 'agent_state':
            if value == 'running':
                self.lbl_agent_status.config(text='● กำลังทำงาน', style='Green.TLabel')
                lbl.config(text='✅ กำลังทำงาน', foreground='green')
            elif value == 'stopped':
                self.lbl_agent_status.config(text='● หยุดอยู่', style='Red.TLabel')
                lbl.config(text='⏹ หยุดแล้ว', foreground='red')
                self.btn_start.config(state='normal')
                self.btn_stop.config(state='disabled')
        elif key == 'smartcard_agent':
            if value == 'connected':
                self.lbl_sc_status.config(text='● Smart Card: เชื่อมต่อแล้ว', style='Green.TLabel')
                lbl.config(text='✅ เชื่อมต่อแล้ว', foreground='green')
            elif value == 'disconnected':
                self.lbl_sc_status.config(text='● Smart Card: ขาดการเชื่อมต่อ', style='Red.TLabel')
                lbl.config(text='❌ ขาดการเชื่อมต่อ', foreground='red')
            else:
                lbl.config(text=f'⚠ {value}', foreground='orange')
        elif key == 'card_present':
            lbl.config(
                text='📥 มีบัตรเสียบอยู่' if value else '📤 ไม่มีบัตร',
                foreground='blue' if value else 'gray',
            )
        elif key == 'cards_processed':
            lbl.config(text=str(value))
        else:
            lbl.config(text=str(value))

    def _log_to_gui(self, level: str, msg: str):
        ts = time.strftime('%H:%M:%S')
        line = f'{ts} [{level}] {msg}\n'
        tag = level
        self.log_text.insert('end', line, tag)
        if self.auto_scroll_var.get():
            self.log_text.see('end')

    def _clear_log(self):
        self.log_text.delete('1.0', 'end')

    def _copy_all_log(self):
        log_content = self.log_text.get('1.0', 'end').strip()
        if log_content:
            self.root.clipboard_clear()
            self.root.clipboard_append(log_content)
            self._log_to_gui('INFO', '📋 คัดลอก log ทั้งหมดแล้ว')

    def _copy_selected_log(self):
        try:
            selected = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self._log_to_gui('INFO', '📋 คัดลอกข้อความที่เลือกแล้ว')
        except tk.TclError:
            self._log_to_gui('WARNING', '⚠️ กรุณาเลือกข้อความก่อนคัดลอก')

    # --- Window / Tray ---
    def _on_close(self):
        self.root.withdraw()
        self._show_tray()

    def _show_tray(self):
        if self.tray_icon:
            return
        try:
            import pystray
            icon_img = _create_tray_icon_image()

            def _show_window(*_):
                if self.tray_icon:
                    self.tray_icon.stop()
                    self.tray_icon = None
                self.root.after(0, self.root.deiconify)

            def _toggle_agent(*_):
                if self.agent_worker and not self.agent_worker.stopped:
                    self.root.after(0, self._stop_agent)
                else:
                    self.root.after(0, self._start_agent)

            def _exit_app(*_):
                if self.agent_worker:
                    self.agent_worker.stop()
                if self.tray_icon:
                    self.tray_icon.stop()
                    self.tray_icon = None
                self.root.after(0, self.root.destroy)

            menu = pystray.Menu(
                pystray.MenuItem('เปิดหน้าต่าง', _show_window, default=True),
                pystray.MenuItem('เริ่ม/หยุด Agent', _toggle_agent),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('ปิดโปรแกรม', _exit_app),
            )
            self.tray_icon = pystray.Icon('nhso_kiosk', icon_img, 'NHSO Kiosk Agent', menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            self._log_to_gui('WARNING', f'ไม่สามารถสร้าง system tray: {e}')
            self.root.deiconify()

    def run(self):
        self._log_to_gui('INFO', f'NHSO Kiosk Agent GUI เริ่มทำงาน')
        self._log_to_gui('INFO', f'Config: {_config_path()}')
        # Auto-start agent after 1 second (let GUI fully load first)
        self.root.after(1000, self._start_agent)
        self.root.mainloop()


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # ตรวจสอบ single instance ก่อนเริ่ม app
    mutex = check_single_instance()
    if mutex is None:
        # มี instance อื่นรันอยู่แล้ว
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "NHSO Kiosk Agent กำลังทำงานอยู่แล้ว\n\nกรุณาตรวจสอบใน Taskbar หรือ System Tray",
            "เปิดซ้ำไม่ได้",
            0x40  # MB_ICONINFORMATION
        )
        sys.exit(1)
    
    app = NHSOKioskApp()
    app.run()
