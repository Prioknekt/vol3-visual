"""
vol3_overview.py
----------------
1. Creates the output JSON file with the required skeleton structure.
2. Polls every second until all three sections are marked done by the
   backend filler scripts via their respective mark_*_done() functions.
3. Once all sections are complete, calls on_analysis_complete().

--- FOR BACKEND DEVS ---
Import and call these three functions when your section is fully written:
    from vol3_overview import mark_base_info_done
    from vol3_overview import mark_programs_done
    from vol3_overview import mark_network_done
"""

import json
import time
import os
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────

OUTPUT_FILE   = "vol3_output.json"
POLL_INTERVAL = 1  # seconds


# ── Skeleton structure ────────────────────────────────────────────────────────

def build_skeleton() -> dict:
    return {
        # Each section has its own done flag.
        # Backend devs flip these via the mark_*_done() functions below.
        "_done": {
            "base_info": False,
            "programs":  False,
            "network":   False,
        },

        "BaseInfo": {
            "os":                    None,
            "file_path_to_mem_file": None,
            "system_info":           {},
        },

        # Keyed by process name. Example entry:
        # "explorer.exe": {
        #     "pid":         1234,
        #     "ppid":        456,
        #     "create_time": "2024-01-15 08:23:11",
        #     "tree": {
        #         "parent":   {"name": "winlogon.exe", "pid": 456},
        #         "children": [{"name": "cmd.exe", "pid": 5678}]
        #     }
        # }
        "Programs": {},

        # List of connection objects. Example entry:
        # {
        #     "proto":        "TCPv4",
        #     "local_addr":   "192.168.1.5",
        #     "local_port":   49320,
        #     "foreign_addr": "142.250.74.46",
        #     "foreign_port": 443,
        #     "state":        "ESTABLISHED",
        #     "pid":          1234,
        #     "owner":        "chrome.exe",
        #     "created":      "2024-01-15 08:25:00"
        # }
        "Network": [],
    }


# ── File helpers ──────────────────────────────────────────────────────────────

def _load() -> dict:
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save(data: dict) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Done functions (backend devs call these) ──────────────────────────────────

def mark_base_info_done() -> None:
    """Call this when BaseInfo has been fully written to the JSON file."""
    _set_done_flag("base_info")

def mark_programs_done() -> None:
    """Call this when Programs has been fully written to the JSON file."""
    _set_done_flag("programs")

def mark_network_done() -> None:
    """Call this when Network has been fully written to the JSON file."""
    _set_done_flag("network")

def _set_done_flag(section: str) -> None:
    try:
        data = _load()
        data["_done"][section] = True
        _save(data)
        print(f"[{_ts()}] + '{section}' marked done.")
    except (OSError, json.JSONDecodeError) as e:
        print(f"[{_ts()}] ERROR marking '{section}' done: {e}")


# ── Completion check ──────────────────────────────────────────────────────────

def _all_done() -> tuple:
    """
    Returns (all_complete, list_of_pending_sections).
    Safe to call while filler scripts are mid-write.
    """
    try:
        data  = _load()
        done  = data.get("_done", {})
        pending = [k for k, v in done.items() if not v]
        return (len(pending) == 0), pending
    except (json.JSONDecodeError, OSError):
        return False, ["<file busy>"]


# ── Completion callback (your visualisation goes here) ────────────────────────

def on_analysis_complete(data: dict) -> None:
    """
    Called once ALL sections are marked done.
    Replace this placeholder with your real visualisation logic.
    """
    print("\n" + "=" * 60)
    print("  Hello World — all sections complete!")
    print("=" * 60)
    print(f"\n  OS           : {data['BaseInfo']['os']}")
    print(f"  Memory file  : {data['BaseInfo']['file_path_to_mem_file']}")
    print(f"  Processes    : {len(data['Programs'])}")
    print(f"  Network conns: {len(data['Network'])}")
    print("\n  Wire up your visualisation here.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Volatility3 Overview — Orchestrator")
    print("=" * 60)

    # Step 1 — create skeleton
    if os.path.exists(OUTPUT_FILE):
        print(f"[WARNING] {OUTPUT_FILE} already exists — overwriting.")
    _save(build_skeleton())
    print(f"[{_ts()}] JSON skeleton created -> {os.path.abspath(OUTPUT_FILE)}")

    # Step 2 — poll until all sections are done
    print(f"[{_ts()}] Waiting for backend scripts "
          f"(polling every {POLL_INTERVAL}s) ...\n")

    last_pending = []
    while True:
        complete, pending = _all_done()
        if complete:
            break

        # Only reprint when the pending list actually changes
        if pending != last_pending:
            waiting_on = ", ".join(pending)
            print(f"[{_ts()}] Still waiting on: {waiting_on}")
            last_pending = pending

        time.sleep(POLL_INTERVAL)

    # Step 3 — fire callback
    print(f"\n[{_ts()}] All sections done — loading results ...")
    on_analysis_complete(_load())


if __name__ == "__main__":
    main()