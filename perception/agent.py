"""Thin entrypoint — implementation is in data/agent.py."""
from pathlib import Path
import runpy

_ROOT = Path(__file__).resolve().parent.parent
runpy.run_path(str(_ROOT / "data" / "agent.py"), run_name="__main__")
