"""
example_filler.py
-----------------
Simulates what your backend scripts will do.
Run this in a second terminal AFTER starting vol3_overview.py.

Each "backend script" imports vol3_overview and calls its mark_*_done()
function once it has finished writing its section to the JSON file.
"""

import json
import time

OUTPUT_FILE = "vol3_output.json"

def load():
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ── Import the done-markers from the orchestrator ─────────────────────────────
from vol3_overview import mark_base_info_done, mark_programs_done, mark_network_done


def fill_base_info():
    print("[filler] Writing BaseInfo ...")
    time.sleep(1)  # simulate analysis time
    data = load()
    data["BaseInfo"]["os"]                    = "Windows 10 x64 (Build 19041)"
    data["BaseInfo"]["file_path_to_mem_file"] = "/cases/case01/memory.raw"
    data["BaseInfo"]["system_info"] = {
        "kernel_base":  "0xf8000280d000",
        "architecture": "AMD64",
        "capture_time": "2024-01-15 08:20:00 UTC",
        "hostname":     "DESKTOP-EXAMPLE",
    }
    save(data)
    mark_base_info_done()   # <-- tell the orchestrator this section is ready


def fill_programs():
    print("[filler] Writing Programs ...")
    time.sleep(2)  # simulate slower analysis
    data = load()
    data["Programs"]["explorer.exe"] = {
        "pid":         2948,
        "ppid":        456,
        "create_time": "2024-01-15 08:21:03",
        "tree": {
            "parent":   {"name": "userinit.exe", "pid": 456},
            "children": [
                {"name": "cmd.exe",    "pid": 5120},
                {"name": "chrome.exe", "pid": 6340},
            ],
        },
        "Strings":{}
    }
    data["Programs"]["cmd.exe"] = {
        "pid":         5120,
        "ppid":        2948,
        "create_time": "2024-01-15 08:23:11",
        "tree": {
            "parent":   {"name": "explorer.exe", "pid": 2948},
            "children": [],
        },
    }
    save(data)
    mark_programs_done()    # <-- tell the orchestrator this section is ready


def fill_network():
    print("[filler] Writing Network ...")
    time.sleep(1)
    data = load()
    data["Network"] = [
        {
            "proto":        "TCPv4",
            "local_addr":   "192.168.1.5",
            "local_port":   49320,
            "foreign_addr": "142.250.74.46",
            "foreign_port": 443,
            "state":        "ESTABLISHED",
            "pid":          6340,
            "owner":        "chrome.exe",
            "created":      "2024-01-15 08:25:00",
        },
        {
            "proto":        "TCPv4",
            "local_addr":   "192.168.1.5",
            "local_port":   49321,
            "foreign_addr": "0.0.0.0",
            "foreign_port": 0,
            "state":        "LISTENING",
            "pid":          4,
            "owner":        "System",
            "created":      "2024-01-15 08:20:05",
        },
    ]
    save(data)
    mark_network_done()     # <-- tell the orchestrator this section is ready

if __name__ == "__main__":
    # In reality each of these would be a separate script.
    # Here we just run them sequentially to demo the flow.
    fill_base_info()
    fill_programs()
    fill_network()
    print("[filler] All sections submitted.")