#!/usr/bin/env python3
"""
qvi_app.py — terminal UI for Quick Volatility3 Interface.

Launched by qvi.py inside the private venv. Don't run this file directly.
"""

from __future__ import annotations
import json
import os
import sys
import subprocess
import threading
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.widgets import (
    Header, Footer, DataTable, Static, Input, RichLog, LoadingIndicator,
    RadioSet, RadioButton, Button,
)
from textual.screen import ModalScreen


HERE = Path(__file__).resolve().parent


class QviTable(DataTable):
    """DataTable variant where right/left/enter forward to app-level actions
    (open / back / open) instead of being eaten by DataTable's internal
    cursor scrolling. Up/Down/j/k still drive the cursor natively."""

    BINDINGS = [
        Binding("up,k",     "cursor_up",   "Up",   show=False),
        Binding("down,j",   "cursor_down", "Down", show=False),
        Binding("home",     "scroll_top",  "Top",  show=False),
        Binding("end",      "scroll_bottom","End", show=False),
        Binding("pageup",   "page_up",     "PgUp", show=False),
        Binding("pagedown", "page_down",   "PgDn", show=False),
        # Forward to app actions so navigation/open works the way the user expects.
        Binding("right",    "app.open",    "Open", show=False),
        Binding("enter",    "app.open",    "Open", show=False),
        Binding("left",     "app.back",    "Back", show=False),
    ]


# ── Plugin catalogue ────────────────────────────────────────────────────────
PLUGINS: list[dict] = [
    dict(id="w_info",     os="windows", label="OS & System Info",
         plugin="windows.info",
         desc="Kernel base, architecture, OS version and build number."),
    dict(id="w_pslist",   os="windows", label="Processes (pslist)",
         plugin="windows.pslist",
         desc="All running processes in the EPROCESS linked list."),
    dict(id="w_pstree",   os="windows", label="Process Tree (pstree)",
         plugin="windows.pstree",
         desc="Parent-child tree.\n\nHighlight a process and press Enter to download its memory segment."),
    dict(id="w_cmdline",  os="windows", label="Command Lines",
         plugin="windows.cmdline",
         desc="Exact command line used to launch each process."),
    dict(id="w_netscan",  os="windows", label="Network (netscan)",
         plugin="windows.netscan",
         desc="Scans memory for open sockets and active connections."),
    dict(id="w_netstat",  os="windows", label="Network (netstat)",
         plugin="windows.netstat",
         desc="TCP/UDP connections and listening ports from kernel structures."),
    dict(id="w_malfind",  os="windows", label="Malfind",
         plugin="windows.malfind",
         desc="Finds hidden/injected/unpacked executable code.\nPrimary malware indicator."),
    dict(id="w_hashdump", os="windows", label="Password Hashes",
         plugin="windows.hashdump",
         desc="Extracts NTLM user password hashes from the registry in memory."),
    dict(id="w_filescan", os="windows", label="File Scanner",
         plugin="windows.filescan",
         desc="Files open or cached in memory at dump time."),
    dict(id="w_dlllist",  os="windows", label="DLL List",
         plugin="windows.dlllist",
         desc="Loaded DLLs per process. Look for unsigned or oddly-named ones."),
    dict(id="w_handles",  os="windows", label="Handles",
         plugin="windows.handles",
         desc="Open handles (files, registry, mutants) per process."),
    dict(id="w_registry", os="windows", label="Registry Hives",
         plugin="windows.registry.hivelist",
         desc="Registry hives loaded in memory."),
    dict(id="w_envars",   os="windows", label="Environment Variables",
         plugin="windows.envars",
         desc="Env vars per process. Useful for finding C2 paths."),
    dict(id="w_svcscan",  os="windows", label="Services",
         plugin="windows.svcscan",
         desc="Windows services in memory. Look for suspicious names."),
    dict(id="w_privs",    os="windows", label="Privileges",
         plugin="windows.privileges",
         desc="Enabled/disabled privileges per process."),

    dict(id="l_banner",   os="linux",   label="OS Banner",
         plugin="linux.banner",
         desc="Linux kernel banner: version, build date, compiler."),
    dict(id="l_pslist",   os="linux",   label="Processes (pslist)",
         plugin="linux.pslist",
         desc="Active processes from the kernel task_struct list."),
    dict(id="l_pstree",   os="linux",   label="Process Tree (pstree)",
         plugin="linux.pstree",
         desc="Parent-child process tree.\n\nHighlight a process and press Enter to download its memory segment."),
    dict(id="l_netstat",  os="linux",   label="Network Connections",
         plugin="linux.netstat",
         desc="TCP/UDP connections from socket structures."),
    dict(id="l_mount",    os="linux",   label="Mounted Filesystems",
         plugin="linux.mount",
         desc="Active mounts and devices."),
    dict(id="l_lsmod",    os="linux",   label="Kernel Modules",
         plugin="linux.lsmod",
         desc="Loaded kernel modules. Look for rootkit drivers."),
    dict(id="l_bash",     os="linux",   label="Bash History",
         plugin="linux.bash",
         desc="Bash command history recovered from process memory."),
    dict(id="l_lsof",     os="linux",   label="Open Files (lsof)",
         plugin="linux.lsof",
         desc="Files open by each process."),
    dict(id="l_maps",     os="linux",   label="Process Maps",
         plugin="linux.proc.Maps",
         desc="Memory mappings per process. Find injected regions."),

    dict(id="m_pslist",   os="mac",     label="Processes (pslist)",
         plugin="mac.pslist",
         desc="Active Mac processes."),
    dict(id="m_pstree",   os="mac",     label="Process Tree (pstree)",
         plugin="mac.pstree",
         desc="Parent-child process relationships.\n\nHighlight a process and press Enter to download its memory segment."),
    dict(id="m_netstat",  os="mac",     label="Network Connections",
         plugin="mac.netstat",
         desc="Active network connections."),
    dict(id="m_lsmod",    os="mac",     label="Kernel Extensions",
         plugin="mac.lsmod",
         desc="Loaded kernel extensions (kexts)."),
    dict(id="m_mount",    os="mac",     label="Mounted Filesystems",
         plugin="mac.mount",
         desc="Active mounts and volumes."),

    dict(id="custom",     os="any",     label="[ Run Custom Command ]",
         plugin="__custom__",
         desc="Type any vol3 plugin and arguments.\n\nExamples:\n  windows.cmdline --pid 1234\n  windows.dumpfiles --pid 1234\n  linux.bash"),
]
PLUGIN_BY_ID = {p["id"]: p for p in PLUGINS}
OS_LABELS    = {"windows": "Windows", "linux": "Linux", "mac": "macOS"}


def plugins_for_os(os_type: str) -> list[dict]:
    return [p for p in PLUGINS if p["os"] in (os_type, "any")]


# ── Cache helpers ──────────────────────────────────────────────────────────
def _cache_path(dump: str) -> Path:
    d = HERE / "projects"
    d.mkdir(exist_ok=True)
    return d / (Path(dump).name.replace(".", "_").replace(" ", "_") + ".json")


def load_cache(dump: str) -> dict:
    p = _cache_path(dump)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(dump: str, cache: dict) -> None:
    _cache_path(dump).write_text(
        json.dumps(cache, indent=2, default=str), encoding="utf-8"
    )


# ── Volatility3 helpers ────────────────────────────────────────────────────
def _vol_script(dump: str, plugin: str, extra: list[str] | None = None,
                output_dir: str | None = None, json_mode: bool = True) -> str:
    argv = ["vol", "-q", "-f", dump]
    if output_dir:
        argv += ["-o", output_dir]
    if json_mode:
        argv += ["-r", "json"]
    argv += [plugin]
    if extra:
        argv += extra
    return (
        "import sys\n"
        "from volatility3 import cli\n"
        f"sys.argv = {json.dumps(argv)}\n"
        "sys.exit(cli.main())\n"
    )


# Windows: hide the subprocess console window so it doesn't flash and steal focus.
_POPEN_KW: dict = {}
if os.name == "nt":
    _POPEN_KW["creationflags"] = subprocess.CREATE_NO_WINDOW


def run_plugin(dump: str, plugin: str) -> tuple[bool, Any]:
    script = _vol_script(dump, plugin)
    try:
        p = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **_POPEN_KW,
        )
        out, err = p.communicate()
        for opener, closer in (("[", "]"), ("{", "}")):
            s, e = out.find(opener), out.rfind(closer)
            if s != -1 and e != -1:
                parsed = json.loads(out[s:e + 1])
                return True, parsed if isinstance(parsed, list) else [parsed]
        return False, (err.strip() or out.strip() or "No data returned.")
    except Exception as ex:
        return False, str(ex)


def run_raw(dump: str, args_str: str) -> str:
    argv = ["vol", "-f", dump] + args_str.split()
    script = (
        "import sys\nfrom volatility3 import cli\n"
        f"sys.argv = {json.dumps(argv)}\n"
        "sys.exit(cli.main())\n"
    )
    try:
        p = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **_POPEN_KW,
        )
        out, err = p.communicate(timeout=300)
        return (out or err or "(no output)").strip()
    except subprocess.TimeoutExpired:
        return "Timed out after 300s."
    except Exception as ex:
        return str(ex)


def detect_os(dump: str) -> str | None:
    script = _vol_script(dump, "banners.Banners")
    try:
        p = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **_POPEN_KW,
        )
        out, err = p.communicate(timeout=90)
        c = (out + err).lower()
        if "windows" in c: return "windows"
        if "darwin" in c or "macos" in c: return "mac"
        if "linux" in c: return "linux"
    except Exception:
        pass
    return None


def dump_segment(dump: str, pid: int | str, os_type: str) -> tuple[bool, str]:
    out_dir = HERE / "dumps" / f"pid_{pid}"
    out_dir.mkdir(parents=True, exist_ok=True)
    plugin = "windows.memmap.Memmap" if os_type == "windows" else "linux.proc.Maps"
    script = _vol_script(
        dump, plugin,
        extra=["--pid", str(pid), "--dump"],
        output_dir=str(out_dir),
    )
    try:
        p = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **_POPEN_KW,
        )
        out, err = p.communicate(timeout=600)
        files = list(out_dir.glob("*"))
        if files:
            lines = "\n".join(
                f"  {f.name}  ({f.stat().st_size:,} B)" for f in files
            )
            return True, f"Saved to:\n  {out_dir}\n\n{lines}"
        return False, (err.strip() or out.strip() or "No files written.")
    except subprocess.TimeoutExpired:
        return False, "Timed out after 600s."
    except Exception as ex:
        return False, str(ex)


# ── Item label formatting & tree depth (kept from original) ────────────────
def make_label(item: dict) -> str:
    pid  = item.get("PID")  or item.get("Pid")
    name = (item.get("ImageFileName") or item.get("COMM") or item.get("Name") or
            item.get("Process") or item.get("Module") or "")
    depth = item.get("__depth", 0)
    ind   = ("  " * depth + "└─ ") if depth else ""

    if item.get("User") and item.get("NTLM"):
        return f"{item['User']}  ·  NTLM: {item['NTLM'][:16]}…"
    if item.get("Args") and name:
        return f"{ind}[{pid}] {name}  ›  {str(item['Args'])[:30]}"
    if item.get("Path") or item.get("FileName"):
        return str(item.get("Path") or item.get("FileName"))[:60]
    if item.get("Command"):
        return f"$ {str(item['Command'])[:58]}"
    if item.get("Variable") and item.get("Value"):
        return f"{item['Variable']} = {str(item['Value'])[:38]}"
    if item.get("Proto") and item.get("LocalAddr"):
        return (f"{item['Proto']}  {item['LocalAddr']}:{item.get('LocalPort','')}"
                f"  -> {item.get('ForeignAddr','*')}:{item.get('ForeignPort','')}"
                f"  {item.get('State','')}")
    if item.get("Mount") or item.get("Device"):
        return f"{item.get('Device','?')} -> {item.get('Mount','?')}"
    if pid is not None and name:
        return f"{ind}[{pid}] {name}"
    vals = [str(v) for v in item.values()
            if isinstance(v, (str, int)) and str(v).strip()]
    return vals[0][:60] if vals else "(item)"


def inject_tree_depth(data: list[dict]) -> list[dict]:
    pid_map = {}
    for item in data:
        pid  = item.get("PID") or item.get("Pid")
        ppid = item.get("PPID") or item.get("Ppid")
        if pid is not None:
            pid_map[pid] = ppid

    def depth(pid, seen=None):
        if seen is None: seen = set()
        if pid in seen: return 0
        seen.add(pid)
        pp = pid_map.get(pid)
        if pp is None or pp == pid or pp == 0 or pp not in pid_map:
            return 0
        return 1 + depth(pp, seen)

    for item in data:
        pid = item.get("PID") or item.get("Pid")
        if pid is not None:
            item["__depth"] = depth(pid)
    return data


# ── Modal: OS picker ───────────────────────────────────────────────────────
class OSPickerScreen(ModalScreen[str]):
    DEFAULT_CSS = """
    OSPickerScreen { align: center middle; }
    #picker {
        width: 50; height: auto; padding: 1 2;
        background: $surface; border: round #cc2222;
    }
    #picker-title { color: #ff4444; text-style: bold; }
    #picker-sub   { color: #777777; margin-bottom: 1; }
    RadioSet { background: $surface; border: none; }
    Button { margin-top: 1; background: #6b0000; color: white; }
    Button:hover { background: #cc2222; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Static("Could not auto-detect OS", id="picker-title")
            yield Static("Select the OS for this memory image:", id="picker-sub")
            yield RadioSet(
                RadioButton("Windows", value=True, id="os-windows"),
                RadioButton("Linux", id="os-linux"),
                RadioButton("macOS", id="os-mac"),
            )
            yield Button("Confirm", id="picker-confirm", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-confirm":
            rs = self.query_one(RadioSet)
            if rs.pressed_button is None:
                self.dismiss("windows")
                return
            mapping = {"os-windows": "windows", "os-linux": "linux", "os-mac": "mac"}
            self.dismiss(mapping.get(rs.pressed_button.id, "windows"))


# ── Modal: custom command input ───────────────────────────────────────────
class CustomCmdScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    CustomCmdScreen { align: center middle; }
    #cmd-box {
        width: 70; height: auto; padding: 1 2;
        background: $surface; border: round #cc2222;
    }
    #cmd-title { color: #ff4444; text-style: bold; margin-bottom: 1; }
    #cmd-help  { color: #777777; margin-bottom: 1; }
    Input { background: #0f0f0f; color: #cccccc; border: round #3a0000; }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel"),
                Binding("enter", "submit", "Run", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="cmd-box"):
            yield Static("Custom vol3 plugin", id="cmd-title")
            yield Static("e.g.  windows.cmdline --pid 1234   |   linux.bash",
                         id="cmd-help")
            yield Input(placeholder="plugin and args", id="cmd-input")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        self.dismiss(val if val else None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        val = self.query_one("#cmd-input", Input).value.strip()
        self.dismiss(val if val else None)


# ── Loading screen for OS detection ────────────────────────────────────────
class DetectScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    DetectScreen { align: center middle; }
    #detect-box {
        width: 60; height: auto; padding: 1 2;
        background: $surface; border: round #cc2222;
    }
    #detect-title { color: #ff4444; text-style: bold; }
    #detect-sub   { color: #cc2222; }
    #detect-file  { color: #555555; margin-bottom: 1; }
    LoadingIndicator { height: 3; color: #cc2222; }
    """

    def __init__(self, dump: str) -> None:
        super().__init__()
        self.dump = dump
        self.result: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="detect-box"):
            yield Static("qvi", id="detect-title")
            yield Static("Identifying memory image...", id="detect-sub")
            yield Static(Path(self.dump).name, id="detect-file")
            yield LoadingIndicator()

    def on_mount(self) -> None:
        def worker():
            r = detect_os(self.dump)
            self.app.call_from_thread(self.dismiss, r)
        threading.Thread(target=worker, daemon=True).start()


# ── Main App ───────────────────────────────────────────────────────────────
class QviApp(App):
    CSS = """
    Screen { background: #0a0a0a; }

    /* Top header info panel */
    #topbar {
        height: 3;
        border: round #cc2222;
        background: #0a0a0a;
        padding: 0 1;
    }
    #topbar-content { width: 100%; height: 1; }
    .topbar-cell { color: #cccccc; padding: 0 1; }
    .topbar-key  { color: #ff4444; text-style: bold; }
    .topbar-sep  { color: #3a0000; }

    /* Main two-column area */
    #main { height: 1fr; }

    #left-panel {
        width: 1fr;
        border: round #cc2222;
        background: #0a0a0a;
    }
    #right-panel {
        width: 80;
        border: round #cc2222;
        background: #0a0a0a;
    }

    /* DataTable styling — terminal/proxmon vibes */
    DataTable {
        background: #0a0a0a;
        color: #cccccc;
    }
    DataTable > .datatable--header {
        background: #0a0a0a;
        color: #ff4444;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #6b0000;
        color: #ffffff;
    }
    DataTable > .datatable--hover {
        background: #1a0000;
    }
    DataTable > .datatable--odd-row { background: #0a0a0a; }
    DataTable > .datatable--even-row { background: #0f0f0f; }

    /* Right-side detail */
    #detail-log {
        background: #0a0a0a;
        color: #cccccc;
        border: none;
        padding: 1;
        scrollbar-color: #cc2222 #0a0a0a;
        scrollbar-background: #0a0a0a;
    }

    /* Bottom raw-output panel */
    #bottom-panel {
        height: 12;
        border: round #cc2222;
        background: #0a0a0a;
    }
    #bottom-log {
        background: #0a0a0a;
        color: #cccccc;
        border: none;
        padding: 0 1;
        scrollbar-color: #cc2222 #0a0a0a;
    }

    /* Footer */
    Footer {
        background: #1a0000;
        color: #cccccc;
    }
    Footer > .footer--key {
        background: #6b0000;
        color: #ffffff;
        text-style: bold;
    }
    Footer > .footer--description {
        color: #cccccc;
        background: #1a0000;
    }

    /* Status pill in top bar */
    #status-pill { color: #cc8800; padding: 0 1; }

    LoadingIndicator { color: #cc2222; }
    """

    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("up,k",        "nav_up",      "Up"),
        Binding("down,j",      "nav_down",    "Down"),
        Binding("right,enter", "open",        "Open"),
        Binding("left,escape", "back",        "Back"),
        Binding("r",           "run_custom",  "Command"),
        Binding("c",           "copy_detail", "Copy"),
        Binding("f",           "refresh_run", "Re-run"),
        Binding("q,ctrl+c",    "quit",        "Quit"),
    ]

    status_text = reactive("")

    def __init__(self, dump: str, cache: dict, detected_os: str) -> None:
        super().__init__()
        self.dump        = dump
        self.cache       = cache
        self.detected_os = detected_os

        self.level: str       = "root"   # "root" or plugin id
        self.vis_plugins      = plugins_for_os(detected_os)
        self.root_rows: list[dict] = []  # [{plugin: dict, cached: bool}]
        self.result_data: list[dict] = []
        self.result_plugin: dict | None = None
        self.list_sel = 0
        self._busy = False

    # ── compose ────────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Container(id="topbar"):
            yield Static(self._topbar_text(), id="topbar-content", markup=True)

        with Horizontal(id="main"):
            with Container(id="left-panel"):
                table = QviTable(
                    id="plugin-table",
                    cursor_type="row",
                    zebra_stripes=True,
                    show_cursor=True,
                )
                yield table
            with Container(id="right-panel"):
                yield RichLog(id="detail-log", markup=True, wrap=True,
                              highlight=False, auto_scroll=False)

        with Container(id="bottom-panel"):
            yield RichLog(id="bottom-log", markup=True, wrap=False,
                          highlight=False, auto_scroll=False)

        yield Footer()

    # ── header text ────────────────────────────────────────────────────────
    def _topbar_text(self) -> str:
        os_label = OS_LABELS.get(self.detected_os, "Unknown")
        name = Path(self.dump).name
        cached_count = sum(1 for p in self.vis_plugins if p["id"] in self.cache)
        sep = "[#3a0000] | [/]"
        status = self.status_text or "ready"
        status_color = "#cc8800" if self.status_text else "#44cc44"
        return (
            f"[#ff4444 bold]qvi[/]  "
            f"{sep}  [#ff4444]OS:[/] [#cccccc]{os_label}[/]  "
            f"{sep}  [#ff4444]Image:[/] [#cccccc]{name}[/]  "
            f"{sep}  [#ff4444]Plugins:[/] [#cccccc]{len(self.vis_plugins)}[/]  "
            f"{sep}  [#ff4444]Cached:[/] [#cc8800]{cached_count}[/]  "
            f"{sep}  [{status_color}]{status}[/]"
        )

    def _refresh_topbar(self) -> None:
        self.query_one("#topbar-content", Static).update(self._topbar_text())

    def watch_status_text(self, _old: str, _new: str) -> None:
        try:
            self._refresh_topbar()
        except Exception:
            pass

    # ── on mount ──────────────────────────────────────────────────────────
    def on_mount(self) -> None:
        self.title = "qvi"
        self.sub_title = Path(self.dump).name
        self._update_bottom_help()

        if self.detected_os:
            self._build_root_table()
            self._update_detail_root()
        else:
            # Detect OS in a background thread so the TUI is already painted.
            self.status_text = "detecting OS..."
            self._bottom_log(
                "[#ff4444 bold]Detecting OS[/]",
                "[#777777]Running banners.Banners (this can take ~30 s)...[/]",
            )

            def worker():
                r = detect_os(self.dump)
                self.call_from_thread(self._on_os_detected, r)

            threading.Thread(target=worker, daemon=True).start()

    def _on_os_detected(self, os_type: str | None) -> None:
        if os_type:
            self._set_os(os_type)
            return
        # Auto-detect failed — show the modal picker.
        self.status_text = "select OS"
        self._bottom_log(
            "[#cc8800]Auto-detect failed.[/]",
            "[#777777]Pick the OS in the dialog to continue.[/]",
        )
        self.push_screen(OSPickerScreen(), self._on_os_picked)

    def _on_os_picked(self, os_type: str | None) -> None:
        # If the user somehow dismissed without choosing, default to windows.
        self._set_os(os_type or "windows")

    def _set_os(self, os_type: str) -> None:
        self.detected_os = os_type
        self.cache["__os__"] = os_type
        save_cache(self.dump, self.cache)
        self.vis_plugins = plugins_for_os(os_type)
        self.status_text = ""
        self._build_root_table()
        self._update_detail_root()
        self._update_bottom_help()
        self._refresh_topbar()

    # ── building tables ───────────────────────────────────────────────────
    def _build_root_table(self) -> None:
        table: DataTable = self.query_one("#plugin-table", DataTable)
        table.clear(columns=True)
        table.add_columns("  ", "Name", "Plugin", "Cached")
        self.root_rows = []
        cur_section = None
        for p in self.vis_plugins:
            section = p["os"].upper() if p["os"] != "any" else "TOOLS"
            if section != cur_section:
                table.add_row(
                    Text(""),
                    Text(f"-- {section} --", style="#ff4444 bold"),
                    Text(""), Text(""),
                )
                self.root_rows.append({"plugin": None, "cached": False})
                cur_section = section
            cached = p["id"] in self.cache
            dot = Text("●", style="#44cc44" if cached else "#555555")
            table.add_row(
                dot,
                Text(p["label"], style="#cccccc"),
                Text(p["plugin"], style="#777777"),
                Text("yes" if cached else "", style="#cc8800"),
            )
            self.root_rows.append({"plugin": p, "cached": cached})

        table.cursor_type = "row"
        # Move cursor past leading section header
        for i, r in enumerate(self.root_rows):
            if r["plugin"] is not None:
                table.move_cursor(row=i)
                self.list_sel = i
                break

    def _build_results_table(self) -> None:
        table: DataTable = self.query_one("#plugin-table", DataTable)
        table.clear(columns=True)
        if not self.result_data:
            table.add_columns("info")
            table.add_row(Text("(no rows returned)", style="#777777"))
            return

        # Pick at most 6 useful columns from the first item's keys
        first = self.result_data[0]
        preferred_keys = [
            "PID", "Pid", "PPID", "Ppid",
            "ImageFileName", "COMM", "Name", "Process", "Module",
            "Args", "Command", "CreateTime", "Path", "FileName",
            "User", "NTLM",
            "Proto", "LocalAddr", "LocalPort", "ForeignAddr", "ForeignPort", "State",
            "Variable", "Value",
            "Mount", "Device",
        ]
        keys = [k for k in preferred_keys if k in first][:6]
        if not keys:
            keys = [k for k in first.keys() if not k.startswith("__")][:6]

        table.add_columns(*[Text(k, style="#ff4444 bold") for k in keys])
        for item in self.result_data:
            cells = []
            for k in keys:
                v = item.get(k, "")
                s = str(v)
                if len(s) > 50:
                    s = s[:47] + "..."
                # Indent first column for tree depth
                if k == keys[0] and "__depth" in item:
                    s = "  " * item["__depth"] + s
                cells.append(Text(s, style="#cccccc"))
            table.add_row(*cells)

        table.cursor_type = "row"
        table.move_cursor(row=0)
        self.list_sel = 0

    # ── detail pane ───────────────────────────────────────────────────────
    def _detail(self) -> RichLog:
        return self.query_one("#detail-log", RichLog)

    def _bottom(self) -> RichLog:
        return self.query_one("#bottom-log", RichLog)

    def _update_detail_root(self) -> None:
        log = self._detail()
        log.clear()
        if not self.root_rows or self.list_sel >= len(self.root_rows):
            return
        row = self.root_rows[self.list_sel]
        if row["plugin"] is None:
            log.write("[#777777]section header[/]")
            return
        cat = row["plugin"]
        log.write(f"[#ff4444 bold]{cat['label']}[/]")
        log.write("")
        log.write(f"[#ff4444]Plugin[/]   [#cccccc]{cat['plugin']}[/]")
        log.write("")
        for line in cat["desc"].split("\n"):
            log.write(f"[#cccccc]{line}[/]")
        if row["cached"]:
            log.write("")
            log.write("[#cc8800]● Cached[/]  [#777777]results available instantly[/]")
            log.write("[#777777]press f to re-run[/]")
        log.write("")
        log.write("[#ff4444 bold]> press Enter / Right to run[/]")

    def _update_detail_result(self) -> None:
        log = self._detail()
        log.clear()
        if not self.result_data or self.list_sel >= len(self.result_data):
            return
        item = self.result_data[self.list_sel]
        is_tree = self.result_plugin and "pstree" in self.result_plugin["plugin"]

        name = (item.get("ImageFileName") or item.get("COMM")
                or item.get("Name") or "item")
        pid = item.get("PID") or item.get("Pid") or ""

        title = f"{name}  [{pid}]" if pid else str(name)
        log.write(f"[#ff4444 bold]{title}[/]")
        log.write("")

        for k, v in item.items():
            if k.startswith("__") or k in ("Offset", "TreeDepth"):
                continue
            sval = str(v)
            if len(sval) > 200:
                sval = sval[:197] + "..."
            log.write(f"[#ff4444]{k:<18}[/] [#cccccc]{sval}[/]")

        if is_tree and pid:
            log.write("")
            log.write("[#3a0000]" + ("-" * 40) + "[/]")
            log.write("[#ff4444 bold]Download Memory Segment[/]")
            log.write(f"[#cccccc]Press Enter / Right to dump PID {pid}[/]")
            log.write(f"[#777777]Output: dumps/pid_{pid}/[/]")

    def _update_bottom_help(self) -> None:
        b = self._bottom()
        b.clear()
        b.write("[#ff4444 bold]Raw output / log[/]")
        b.write("[#777777]Plugin output and status messages will appear here.[/]")
        b.write("")
        b.write(f"[#777777]Image:[/] [#cccccc]{self.dump}[/]")
        b.write(f"[#777777]Cache:[/] [#cccccc]{_cache_path(self.dump)}[/]")

    def _bottom_log(self, *lines: str) -> None:
        b = self._bottom()
        b.clear()
        for ln in lines:
            b.write(ln)

    # ── selection tracking ────────────────────────────────────────────────
    def on_data_table_row_highlighted(self,
                                      event: DataTable.RowHighlighted) -> None:
        try:
            idx = event.cursor_row
        except Exception:
            return
        if self.level == "root":
            # If we landed on a section header, step in the direction of
            # travel (away from the previous selection) onto a real row.
            if (idx < len(self.root_rows)
                    and self.root_rows[idx]["plugin"] is None):
                direction = 1 if idx >= self.list_sel else -1
                new_idx = self._next_plugin_row(idx, direction)
                if new_idx is None:
                    # No row in that direction — try the other way.
                    new_idx = self._next_plugin_row(idx, -direction)
                if new_idx is not None:
                    self.list_sel = new_idx
                    table: DataTable = self.query_one("#plugin-table", DataTable)
                    self.call_after_refresh(lambda i=new_idx: table.move_cursor(row=i))
                    self._update_detail_root()
                return
            self.list_sel = idx
            self._update_detail_root()
        else:
            self.list_sel = idx
            self._update_detail_result()

    def _next_plugin_row(self, start: int, direction: int) -> int | None:
        """Return the index of the next non-section row from `start`, walking by
        `direction` (+1 or -1). None if no such row exists."""
        n = len(self.root_rows)
        idx = start + direction
        while 0 <= idx < n:
            if self.root_rows[idx]["plugin"] is not None:
                return idx
            idx += direction
        return None

    def on_data_table_row_selected(self,
                                   event: DataTable.RowSelected) -> None:
        # Enter / double-click on a row
        self.action_open()

    # ── actions ───────────────────────────────────────────────────────────
    def action_nav_up(self) -> None:
        if self._busy: return
        table: DataTable = self.query_one("#plugin-table", DataTable)
        if self.level == "root":
            n = len(self.root_rows)
            idx = max(0, self.list_sel - 1)
            while idx > 0 and self.root_rows[idx]["plugin"] is None:
                idx -= 1
            if 0 <= idx < n and self.root_rows[idx]["plugin"] is None:
                return
            table.move_cursor(row=idx)
        else:
            idx = max(0, self.list_sel - 1)
            table.move_cursor(row=idx)

    def action_nav_down(self) -> None:
        if self._busy: return
        table: DataTable = self.query_one("#plugin-table", DataTable)
        if self.level == "root":
            n = len(self.root_rows)
            idx = min(n - 1, self.list_sel + 1)
            while idx < n - 1 and self.root_rows[idx]["plugin"] is None:
                idx += 1
            if self.root_rows[idx]["plugin"] is None:
                return
            table.move_cursor(row=idx)
        else:
            idx = min(len(self.result_data) - 1, self.list_sel + 1)
            table.move_cursor(row=idx)

    def action_open(self) -> None:
        if self._busy: return
        if self.level == "root":
            if self.list_sel >= len(self.root_rows): return
            cat = self.root_rows[self.list_sel]["plugin"]
            if cat is None: return
            if cat["plugin"] == "__custom__":
                self.action_run_custom(); return
            self._load_plugin(cat)
        else:
            if not self.result_plugin: return
            is_tree = "pstree" in self.result_plugin["plugin"]
            if is_tree and self.result_data:
                item = self.result_data[self.list_sel]
                pid = item.get("PID") or item.get("Pid")
                if pid:
                    self._download_segment(pid)

    def action_back(self) -> None:
        if self._busy: return
        if self.level == "root":
            return
        self.level = "root"
        self.result_data = []
        self.result_plugin = None
        self.list_sel = 0
        self._build_root_table()
        self._update_detail_root()
        self._update_bottom_help()
        self._refresh_topbar()

    def action_run_custom(self) -> None:
        if self._busy: return
        def cb(args: str | None) -> None:
            if not args: return
            self._busy = True
            self.status_text = f"running: {args}"
            self._bottom_log(
                f"[#ff4444 bold]$ {args}[/]",
                "[#777777]running...[/]",
            )

            def worker():
                out = run_raw(self.dump, args)
                self.call_from_thread(self._custom_done, args, out)
            threading.Thread(target=worker, daemon=True).start()

        self.push_screen(CustomCmdScreen(), cb)

    def _custom_done(self, args: str, out: str) -> None:
        self._busy = False
        self.status_text = ""
        b = self._bottom()
        b.clear()
        b.write(f"[#ff4444 bold]$ {args}[/]")
        b.write("")
        for line in out[:8000].split("\n"):
            b.write(f"[#cccccc]{line}[/]")

    def action_copy_detail(self) -> None:
        # Best-effort clipboard copy. Falls back gracefully.
        try:
            log = self._detail()
            # RichLog stores lines; concat plain text
            lines = []
            for line in log.lines:
                try:
                    lines.append(line.text)
                except Exception:
                    lines.append(str(line))
            text = "\n".join(lines)
            self.copy_to_clipboard(text)
            self.status_text = "copied"
            self.set_timer(1.5, lambda: setattr(self, "status_text", ""))
        except Exception as ex:
            self.status_text = f"copy failed: {ex}"
            self.set_timer(2.0, lambda: setattr(self, "status_text", ""))

    def action_refresh_run(self) -> None:
        if self._busy: return
        if self.level != "root": return
        if self.list_sel >= len(self.root_rows): return
        cat = self.root_rows[self.list_sel]["plugin"]
        if cat is None or cat["plugin"] == "__custom__": return
        # Force re-run by dropping cache entry
        if cat["id"] in self.cache:
            del self.cache[cat["id"]]
            save_cache(self.dump, self.cache)
        self._load_plugin(cat)

    # ── plugin loading ───────────────────────────────────────────────────
    def _load_plugin(self, cat: dict) -> None:
        if cat["id"] in self.cache:
            self._show_results(cat, self.cache[cat["id"]])
            return

        self._busy = True
        self.status_text = f"running {cat['plugin']}"

        # Show prominent feedback in the detail pane so the user sees something
        # happen the instant they press Enter.
        log = self._detail()
        log.clear()
        log.write(f"[#ff4444 bold]Running {cat['label']}[/]")
        log.write("")
        log.write(f"[#cccccc]Plugin:  {cat['plugin']}[/]")
        log.write(f"[#cccccc]Image:   {Path(self.dump).name}[/]")
        log.write("")
        log.write("[#cc8800]Working...[/] [#777777]vol3 may take 30 s to several minutes.[/]")
        log.write("[#777777]The first plugin is the slowest because vol3 builds its symbol cache.[/]")

        self._bottom_log(
            f"[#ff4444 bold]Running {cat['plugin']}[/]",
            "[#777777]This may take a few minutes...[/]",
        )

        def worker():
            ok, data = run_plugin(self.dump, cat["plugin"])
            self.call_from_thread(self._plugin_done, cat, ok, data)

        threading.Thread(target=worker, daemon=True).start()

    def _plugin_done(self, cat: dict, ok: bool, data: Any) -> None:
        self._busy = False
        self.status_text = ""
        if ok:
            self.cache[cat["id"]] = data
            save_cache(self.dump, self.cache)
            self._show_results(cat, data)
            self._bottom_log(
                f"[#44cc44]Done[/]  [#cccccc]{cat['plugin']}[/] -> "
                f"[#cccccc]{len(data)} rows[/]"
            )
        else:
            self._detail().clear()
            self._detail().write("[#ff4444 bold]Error[/]")
            self._detail().write("")
            self._detail().write(f"[#cccccc]{str(data)[:2000]}[/]")
            self._detail().write("")
            self._detail().write("[#777777]press Left/Esc to go back[/]")
            self._bottom_log(f"[#ff4444]Error:[/] [#cccccc]{str(data)[:300]}[/]")

    def _show_results(self, cat: dict, data: list[dict]) -> None:
        if "pstree" in cat["plugin"]:
            data = inject_tree_depth(data)
            self.cache[cat["id"]] = data

        self.level = cat["id"]
        self.result_data = data
        self.result_plugin = cat
        self.list_sel = 0
        self._build_results_table()
        self._update_detail_result()
        self._refresh_topbar()

    # ── segment download ─────────────────────────────────────────────────
    def _download_segment(self, pid: int | str) -> None:
        self._busy = True
        self.status_text = f"dumping pid {pid}"
        self._bottom_log(
            f"[#ff4444 bold]Downloading memory segment for PID {pid}[/]",
            "[#777777]This may take several minutes...[/]",
        )

        def worker():
            ok, msg = dump_segment(self.dump, pid, self.detected_os)
            self.call_from_thread(self._download_done, pid, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _download_done(self, pid, ok: bool, msg: str) -> None:
        self._busy = False
        self.status_text = ""
        b = self._bottom()
        b.clear()
        if ok:
            b.write(f"[#44cc44 bold]Segment dumped — PID {pid}[/]")
        else:
            b.write(f"[#ff4444 bold]Segment dump failed — PID {pid}[/]")
        b.write("")
        for line in str(msg).split("\n"):
            b.write(f"[#cccccc]{line}[/]")


# ── entry ─────────────────────────────────────────────────────────────────
def _prompt_dump_path() -> str | None:
    print("qvi - terminal volatility3 frontend")
    print()
    try:
        path = input("path to memory dump: ").strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        return None
    return path or None


def main() -> None:
    args = sys.argv[1:]
    fresh = "--fresh" in args
    args = [a for a in args if a != "--fresh"]

    if not args:
        dump = _prompt_dump_path()
        if not dump:
            sys.exit(0)
    else:
        dump = args[0]

    if not os.path.exists(dump):
        print(f"[qvi] file not found: {dump}")
        sys.exit(1)

    cache = {} if fresh else load_cache(dump)
    detected_os = "" if fresh else cache.get("__os__", "")

    # The TUI itself handles auto-detection and the OS picker modal.
    # No pre-launch input() prompts — they conflict with Windows terminals
    # and with Textual taking over the screen.
    app = QviApp(dump, cache, detected_os)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback
        log = HERE / "qvi_crash.log"
        log.write_text(traceback.format_exc())
        print(f"\n[qvi] crashed - details in {log}")
        sys.exit(1)
