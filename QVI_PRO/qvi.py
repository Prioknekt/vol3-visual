#!/usr/bin/env python3
"""
qvi.py - Quick Volatility3 Interface (terminal edition)

Self-bootstrapping launcher:
  * Creates a private virtualenv next to this file (./.qvi-venv)
  * Installs textual, rich, volatility3, pycryptodome inside that venv
  * Pre-fetches volatility3 symbol packs (windows / linux / mac) for offline use
  * Runs app.py inside that venv as a child process

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
import urllib.request
import zipfile
from pathlib import Path

HERE     = Path(__file__).resolve().parent
VENV_DIR = HERE / ".qvi-venv"
MARKER   = VENV_DIR / ".qvi-ready"
SYMBOLS_MARKER = VENV_DIR / ".qvi-symbols-ready"
APP_FILE = HERE / "app.py"
REQS     = ["textual>=0.60", "rich>=13.7", "volatility3>=2.7", "pycryptodome"]

SYMBOL_URLS = {
    "windows.zip": "https://downloads.volatilityfoundation.org/volatility3/symbols/windows.zip",
    "linux.zip":   "https://downloads.volatilityfoundation.org/volatility3/symbols/linux.zip",
    "mac.zip":     "https://downloads.volatilityfoundation.org/volatility3/symbols/mac.zip",
}


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


def _symbol_cache_dir() -> Path:
    """Volatility3 standard symbol cache location."""
    if os.name == "nt":
        local = os.getenv("LOCALAPPDATA")
        if local:
            return Path(local) / "volatility3" / "symbols"
    return Path.home() / ".cache" / "volatility3" / "symbols"


def _ensure_symbols() -> None:
    """
    Pre-download the windows/linux/mac symbol zips so vol3 can resolve
    structures (and hashdump can decrypt) offline. Idempotent and quiet
    on subsequent runs.
    """
    if SYMBOLS_MARKER.exists():
        return

    cache_dir = _symbol_cache_dir()
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[qvi] could not create symbol cache dir {cache_dir}: {e}")
        return

    any_downloaded = False
    for name, url in SYMBOL_URLS.items():
        zip_path = cache_dir / name
        if zip_path.exists():
            continue
        any_downloaded = True
        print(f"[qvi] downloading {name} (one-time) ...", flush=True)
        try:
            urllib.request.urlretrieve(url, zip_path)
        except Exception as e:
            print(f"[qvi] failed to download {name}: {e}")
            continue
        # vol3 can read the zip directly, but extracting helps some plugins.
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(cache_dir)
        except Exception as e:
            print(f"[qvi] note: could not extract {name}: {e}")

    if any_downloaded:
        print("[qvi] symbols ready.", flush=True)

    try:
        SYMBOLS_MARKER.write_text("ok", encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    if not APP_FILE.exists():
        print(f"[qvi] cannot find {APP_FILE.name} next to qvi.py")
        sys.exit(1)

    if _in_our_venv():
        # Already inside the venv -- run the app in-process.
        # Symbols still need ensuring on the first run inside the venv.
        _ensure_symbols()
        sys.argv[0] = str(APP_FILE)
        ns = {"__name__": "__main__", "__file__": str(APP_FILE)}
        with open(APP_FILE, "r", encoding="utf-8") as f:
            code = compile(f.read(), str(APP_FILE), "exec")
        exec(code, ns)
        return

    py = _ensure_venv()
    _ensure_symbols()

    # Run the app as a *child* process and wait. This keeps stdin/stdout
    # attached to the same terminal -- critical on Windows where os.execv
    # detaches and returns control to the shell prematurely.
    cmd = [str(py), str(APP_FILE), *sys.argv[1:]]
    try:
        rc = subprocess.call(cmd)
    except KeyboardInterrupt:
        rc = 130
    sys.exit(rc)


if __name__ == "__main__":
    main()
