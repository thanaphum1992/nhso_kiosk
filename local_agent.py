"""
Legacy copy of the kiosk local agent — kept in sync with agent_อ่านบัตร/local_agent.py (poll + Smart Card Agent :8189).
Prefer running the copy inside agent_อ่านบัตร/ via Card_reader_agent.bat.
"""
from pathlib import Path
import runpy

_agent_dir = Path(__file__).resolve().parent / "agent_อ่านบัตร"
_script = _agent_dir / "local_agent.py"
if not _script.is_file():
    raise SystemExit(f"agent script not found: {_script}")

runpy.run_path(str(_script), run_name="__main__")
