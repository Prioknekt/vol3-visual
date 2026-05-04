"""
vol3_overview.py
----------------
Usage:
    python vol3_overview.py <path_to_mem_dump> [--output-dir <dir>]

Examples:
    python vol3_overview.py /cases/case01/memory.raw
    python vol3_overview.py /cases/case01/memory.raw --output-dir /cases/results

What it does:
    1. Creates a JSON file in the output directory named after the mem dump
       e.g. memory.raw  ->  <output_dir>/memory.json
    2. Polls every second until backend scripts mark all three sections done
       via mark_base_info_done(), mark_programs_done(), mark_network_done()
    3. Calls on_analysis_complete(data, json_path) — wire your GUI launch here

--- FOR BACKEND DEVS ---
Import and call these three functions when your section is fully written:
    from vol3_overview import mark_base_info_done
    from vol3_overview import mark_programs_done
    from vol3_overview import mark_network_done

The JSON path is stored in OUTPUT_FILE once the script has started.
"""

import json
import time
import os
import argparse
from datetime import datetime

# ── Set by main() after argument parsing ─────────────────────────────────────
OUTPUT_FILE = None   # full path to the active JSON file
POLL_INTERVAL = 1    # seconds


# ── Skeleton structure ────────────────────────────────────────────────────────

def build_skeleton(mem_path: str) -> dict:
    return {
        "_done": {
            "base_info": False,
            "programs":  False,
            "network":   False,
        },
        "BaseInfo": {
            "os":                    None,
            "file_path_to_mem_file": mem_path,
            "system_info":           {},
        },
        "Programs": {},
        "Network":  [],
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
    if OUTPUT_FILE is None:
        print(f"[ERROR] OUTPUT_FILE not set — did you call main() first?")
        return
    try:
        data = _load()
        data["_done"][section] = True
        _save(data)
        print(f"[{_ts()}] + '{section}' marked done.")
    except (OSError, json.JSONDecodeError) as e:
        print(f"[{_ts()}] ERROR marking '{section}' done: {e}")


# ── Completion check ──────────────────────────────────────────────────────────

def _all_done() -> tuple:
    try:
        data    = _load()
        done    = data.get("_done", {})
        pending = [k for k, v in done.items() if not v]
        return (len(pending) == 0), pending
    except (json.JSONDecodeError, OSError):
        return False, ["<file busy>"]


# ── Completion callback ───────────────────────────────────────────────────────

def on_analysis_complete(data: dict, json_path: str) -> None:
    """
    Called once ALL sections are marked done.

    `data`      — the fully populated dict
    `json_path` — absolute path to the finished JSON file
                  pass this as the argument to your GUI script, e.g.:
                  subprocess.Popen(["python", "gui.py", json_path])
    """
    print("\n" + "=" * 60)
    print("  Hello World — all sections complete!")
    print("=" * 60)
    print(f"\n  JSON saved to  : {json_path}")
    print(f"  OS             : {data['BaseInfo']['os']}")
    print(f"  Memory file    : {data['BaseInfo']['file_path_to_mem_file']}")
    print(f"  Processes      : {len(data['Programs'])}")
    print(f"  Network conns  : {len(data['Network'])}")
    print("\n  Launch your GUI here, e.g.:")
    print(f"  subprocess.Popen(['python', 'gui.py', '{json_path}'])")


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Volatility3 Overview — orchestrator"
    )
    parser.add_argument(
        "mem_dump",
        help="Path to the memory dump file (e.g. /cases/case01/memory.raw)"
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    global OUTPUT_FILE

    args = parse_args()

    mem_path = os.path.abspath(args.mem_dump)

    # Fixed output directory: ./output/ next to this script
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

    # Timestamp-based filename (e.g. 2024-01-15_08-20-00.json)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_name = timestamp + ".json"

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    OUTPUT_FILE = os.path.join(output_dir, json_name)

    print("=" * 60)
    print("  Volatility3 Overview — Orchestrator")
    print("=" * 60)
    print(f"  Mem dump   : {mem_path}")
    print(f"  Output dir : {output_dir}")
    print(f"  JSON file  : {OUTPUT_FILE}")
    print("=" * 60 + "\n")

    # Step 1 — create skeleton JSON
    if os.path.exists(OUTPUT_FILE):
        print(f"[WARNING] {OUTPUT_FILE} already exists — overwriting.")
    _save(build_skeleton(mem_path))
    print(f"[{_ts()}] JSON skeleton created.")

    # Step 2 — poll until all sections are done
    print(f"[{_ts()}] Waiting for backend scripts (polling every {POLL_INTERVAL}s) ...\n")

    last_pending = []
    while True:
        complete, pending = _all_done()
        if complete:
            break
        if pending != last_pending:
            print(f"[{_ts()}] Still waiting on: {', '.join(pending)}")
            last_pending = pending
        time.sleep(POLL_INTERVAL)

    # Step 3 — fire callback
    print(f"\n[{_ts()}] All sections done — loading results ...")
    on_analysis_complete(_load(), OUTPUT_FILE)


if __name__ == "__main__":
    main()