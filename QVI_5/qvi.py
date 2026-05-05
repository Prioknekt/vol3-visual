#!/usr/bin/env python3
"""
qvi.py — Quick Volatility3 Interface (terminal edition)

Self-bootstrapping launcher:
  • Creates a private virtualenv next to this file (./.qvi-venv)
  • Installs textual, rich, volatility3 inside that venv
  • Runs qvi_app.py inside that venv as a child process

Works on Linux and Windows (PowerShell / cmd / Bash).
Just run:
    python qvi.py <dump.mem>
    python qvi.py <dump.mem> --fresh
    python qvi.py                   # opens an OS / file picker in the TUI
"""

from __future__ import annotations
import os
import sys
import subprocess
from pathlib import Path

HERE     = Path(__file__).resolve().parent
VENV_DIR = HERE / ".qvi-venv"
MARKER   = VENV_DIR / ".qvi-ready"
APP_FILE = HERE / "qvi_app.py"
REQS     = ["textual>=0.60", "rich>=13.7", "volatility3>=2.7"]


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _in_our_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == _venv_python().resolve()
    except Exception:
        return False


def _ensure_venv() -> Path:
    """Make sure the venv exists and dependencies are installed. Return its python path."""
    py = _venv_python()

    if not py.exists():
        print("[qvi] creating virtualenv ...", flush=True)
        import venv
        try:
            venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=False).create(VENV_DIR)
        except Exception as e:
            print(f"[qvi] failed to create venv: {e}")
            sys.exit(1)

    if not py.exists():
        print(f"[qvi] venv python missing at {py}")
        sys.exit(1)

    if not MARKER.exists():
        print("[qvi] installing dependencies (one-time, ~30 s) ...", flush=True)
        try:
            subprocess.check_call(
                [str(py), "-m", "pip", "install", "--upgrade", "pip"],
                stdout=subprocess.DEVNULL,
            )
            subprocess.check_call([str(py), "-m", "pip", "install", *REQS])
        except subprocess.CalledProcessError as e:
            print(f"[qvi] dependency install failed: {e}")
            sys.exit(1)
        MARKER.write_text("ok", encoding="utf-8")

    return py


def main() -> None:
    if not APP_FILE.exists():
        print(f"[qvi] cannot find {APP_FILE.name} next to qvi.py")
        sys.exit(1)

    if _in_our_venv():
        # Already inside the venv — run the app in-process.
        sys.argv[0] = str(APP_FILE)
        ns = {"__name__": "__main__", "__file__": str(APP_FILE)}
        with open(APP_FILE, "r", encoding="utf-8") as f:
            code = compile(f.read(), str(APP_FILE), "exec")
        exec(code, ns)
        return

    py = _ensure_venv()

    # Run the app as a *child* process and wait. This keeps stdin/stdout
    # attached to the same terminal — critical on Windows where os.execv
    # detaches and returns control to the shell prematurely.
    cmd = [str(py), str(APP_FILE), *sys.argv[1:]]
    try:
        rc = subprocess.call(cmd)
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
