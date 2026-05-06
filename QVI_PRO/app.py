#!/usr/bin/env python3
"""
app.py - terminal UI for Quick Volatility3 Interface.

Launched by qvi.py inside the private venv. Don't run this file directly
unless you've already installed textual / rich / volatility3 yourself.
"""

from __future__ import annotations
import json
import os
import sys
import subprocess
import threading
import datetime as _dt
from pathlib import Path
from typing import Any

from rich.text import Text
from rich.markup import escape as _markup_escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.reactive import reactive
from textual.widgets import (
    Header, Footer, DataTable, Static, Input, RichLog,
    RadioSet, RadioButton, Button, Checkbox,
)
from textual.screen import ModalScreen


HERE = Path(__file__).resolve().parent
DUMP_DIR_NAME = "dumped"


# ── Themes ────────────────────────────────────────────────────────────────
# Each theme is a flat dict of named colors. CSS is built from the active
# theme. The default ("dark_red") matches the original look.
THEMES: dict[str, dict] = {
    "dark_red": {
        "label":      "Dark / Red (default)",
        "bg":         "#0a0a0a",
        "panel_bg":   "#0a0a0a",
        "alt_row":    "#0f0f0f",
        "border":     "#cc2222",
        "accent":     "#ff4444",
        "accent_dim": "#cc2222",
        "accent_dark":"#3a0000",
        "cursor_bg":  "#6b0000",
        "cursor_fg":  "#ffffff",
        "hover_bg":   "#1a0000",
        "fg":         "#cccccc",
        "fg_dim":     "#777777",
        "fg_faint":   "#555555",
        "ok":         "#44cc44",
        "warn":       "#cc8800",
        "footer_bg":  "#1a0000",
        "input_bg":   "#0f0f0f",
        "input_border":"#3a0000",
        "btn_bg":     "#6b0000",
        "btn_hover":  "#cc2222",
    },
    "dark_blue": {
        "label":      "Dark / Blue",
        "bg":         "#08101a",
        "panel_bg":   "#08101a",
        "alt_row":    "#0c1422",
        "border":     "#2266cc",
        "accent":     "#4488ff",
        "accent_dim": "#2266cc",
        "accent_dark":"#0a1f3a",
        "cursor_bg":  "#003a7a",
        "cursor_fg":  "#ffffff",
        "hover_bg":   "#0a1f3a",
        "fg":         "#cccccc",
        "fg_dim":     "#778899",
        "fg_faint":   "#555a66",
        "ok":         "#44cc88",
        "warn":       "#ffaa33",
        "footer_bg":  "#0a1f3a",
        "input_bg":   "#0c1422",
        "input_border":"#0a1f3a",
        "btn_bg":     "#003a7a",
        "btn_hover":  "#2266cc",
    },
    "dark_green": {
        "label":      "Dark / Green (matrix)",
        "bg":         "#08120a",
        "panel_bg":   "#08120a",
        "alt_row":    "#0c1810",
        "border":     "#22aa44",
        "accent":     "#44ee66",
        "accent_dim": "#22aa44",
        "accent_dark":"#0a2210",
        "cursor_bg":  "#0a5520",
        "cursor_fg":  "#ffffff",
        "hover_bg":   "#0a2210",
        "fg":         "#cccccc",
        "fg_dim":     "#778877",
        "fg_faint":   "#556655",
        "ok":         "#44ee66",
        "warn":       "#ddcc33",
        "footer_bg":  "#0a2210",
        "input_bg":   "#0c1810",
        "input_border":"#0a2210",
        "btn_bg":     "#0a5520",
        "btn_hover":  "#22aa44",
    },
    "dark_amber": {
        "label":      "Dark / Amber",
        "bg":         "#0e0a06",
        "panel_bg":   "#0e0a06",
        "alt_row":    "#14100a",
        "border":     "#cc7722",
        "accent":     "#ffaa44",
        "accent_dim": "#cc7722",
        "accent_dark":"#3a2206",
        "cursor_bg":  "#6b3a00",
        "cursor_fg":  "#ffffff",
        "hover_bg":   "#1a1006",
        "fg":         "#d8c8b0",
        "fg_dim":     "#998866",
        "fg_faint":   "#665544",
        "ok":         "#aacc44",
        "warn":       "#ffcc66",
        "footer_bg":  "#1a1006",
        "input_bg":   "#14100a",
        "input_border":"#3a2206",
        "btn_bg":     "#6b3a00",
        "btn_hover":  "#cc7722",
    },
    "light": {
        "label":      "Light",
        "bg":         "#f5f5f0",
        "panel_bg":   "#ffffff",
        "alt_row":    "#f0f0ec",
        "border":     "#aa2222",
        "accent":     "#cc2222",
        "accent_dim": "#aa2222",
        "accent_dark":"#e8d0d0",
        "cursor_bg":  "#cc2222",
        "cursor_fg":  "#ffffff",
        "hover_bg":   "#f0e0e0",
        "fg":         "#222222",
        "fg_dim":     "#666666",
        "fg_faint":   "#999999",
        "ok":         "#118822",
        "warn":       "#aa6600",
        "footer_bg":  "#e8d0d0",
        "input_bg":   "#ffffff",
        "input_border":"#aa2222",
        "btn_bg":     "#cc2222",
        "btn_hover":  "#aa2222",
    },
}
DEFAULT_THEME = "dark_red"
THEME_ORDER = ["dark_red", "dark_blue", "dark_green", "dark_amber", "light"]


def _theme_settings_path() -> Path:
    return HERE / ".qvi-theme"


def load_theme_name() -> str:
    p = _theme_settings_path()
    if p.exists():
        try:
            name = p.read_text(encoding="utf-8").strip()
            if name in THEMES:
                return name
        except Exception:
            pass
    return DEFAULT_THEME


def save_theme_name(name: str) -> None:
    try:
        _theme_settings_path().write_text(name, encoding="utf-8")
    except Exception:
        pass


def build_css(t: dict) -> str:
    """Render the app stylesheet from a theme dictionary."""
    return f"""
    Screen {{ background: {t['bg']}; color: {t['fg']}; }}

    /* Top header info panel */
    #topbar {{
        height: 3;
        border: round {t['border']};
        background: {t['panel_bg']};
        padding: 0 1;
    }}
    #topbar-content {{ width: 100%; height: 1; }}

    /* Main two-column area */
    #main {{ height: 1fr; }}

    #left-panel {{
        width: 1fr;
        border: round {t['border']};
        background: {t['panel_bg']};
    }}
    #right-panel {{
        width: 80;
        border: round {t['border']};
        background: {t['panel_bg']};
    }}

    /* Filter bar at top of left panel */
    #filter-bar {{
        height: 3;
        background: {t['panel_bg']};
        padding: 0 1;
    }}
    #filter-input {{
        background: {t['input_bg']};
        color: {t['fg']};
        border: round {t['input_border']};
        height: 3;
    }}
    #filter-input:focus {{
        border: round {t['accent']};
    }}

    /* DataTable styling */
    DataTable {{
        background: {t['panel_bg']};
        color: {t['fg']};
        scrollbar-color: {t['border']};
        scrollbar-color-hover: {t['accent']};
        scrollbar-color-active: {t['accent']};
        scrollbar-background: {t['panel_bg']};
        scrollbar-background-hover: {t['panel_bg']};
        scrollbar-background-active: {t['panel_bg']};
        scrollbar-corner-color: {t['panel_bg']};
        scrollbar-size: 1 1;
    }}
    DataTable > .datatable--header {{
        background: {t['panel_bg']};
        color: {t['accent']};
        text-style: bold;
    }}
    DataTable > .datatable--cursor {{
        background: {t['cursor_bg']};
        color: {t['cursor_fg']};
    }}
    DataTable > .datatable--hover {{
        background: {t['hover_bg']};
    }}
    DataTable > .datatable--odd-row {{ background: {t['panel_bg']}; }}
    DataTable > .datatable--even-row {{ background: {t['alt_row']}; }}

    /* Right-side detail */
    #detail-log {{
        background: {t['panel_bg']};
        color: {t['fg']};
        border: none;
        padding: 1;
        scrollbar-color: {t['border']};
        scrollbar-color-hover: {t['accent']};
        scrollbar-color-active: {t['accent']};
        scrollbar-background: {t['panel_bg']};
        scrollbar-background-hover: {t['panel_bg']};
        scrollbar-background-active: {t['panel_bg']};
        scrollbar-corner-color: {t['panel_bg']};
        scrollbar-size: 1 1;
    }}

    /* Bottom raw-output panel */
    #bottom-panel {{
        height: 12;
        border: round {t['border']};
        background: {t['panel_bg']};
    }}
    #bottom-log {{
        background: {t['panel_bg']};
        color: {t['fg']};
        border: none;
        padding: 0 1;
        scrollbar-color: {t['border']};
        scrollbar-color-hover: {t['accent']};
        scrollbar-color-active: {t['accent']};
        scrollbar-background: {t['panel_bg']};
        scrollbar-background-hover: {t['panel_bg']};
        scrollbar-background-active: {t['panel_bg']};
        scrollbar-corner-color: {t['panel_bg']};
        scrollbar-size: 1 1;
    }}

    /* Footer */
    Footer {{
        background: {t['footer_bg']};
        color: {t['fg']};
    }}
    Footer > .footer--key {{
        background: {t['btn_bg']};
        color: {t['cursor_fg']};
        text-style: bold;
    }}
    Footer > .footer--description {{
        color: {t['fg']};
        background: {t['footer_bg']};
    }}

    LoadingIndicator {{ color: {t['accent_dim']}; }}

    /* Modal: OS picker */
    OSPickerScreen {{ align: center middle; }}
    #picker {{
        width: 54; height: auto; padding: 1 2;
        background: {t['panel_bg']}; border: round {t['border']};
    }}
    #picker-title {{ color: {t['accent']}; text-style: bold; }}
    #picker-sub   {{ color: {t['fg_dim']}; margin-bottom: 1; }}
    #picker RadioSet {{
        background: {t['panel_bg']};
        border: none;
        height: auto;
        padding: 0;
    }}
    #picker RadioButton {{
        background: {t['panel_bg']};
        color: {t['fg']};
        border: none;
        padding: 0 1;
    }}
    #picker RadioButton:hover {{
        background: {t['hover_bg']};
    }}
    #picker RadioButton.-on > .toggle--button {{
        color: {t['accent']};
        background: {t['panel_bg']};
    }}
    #picker RadioButton > .toggle--button {{
        color: {t['fg_dim']};
        background: {t['panel_bg']};
    }}
    #picker RadioButton:focus {{
        background: {t['hover_bg']};
        text-style: bold;
    }}
    #picker Button {{
        margin-top: 1;
        background: {t['btn_bg']};
        color: {t['cursor_fg']};
        border: none;
    }}
    #picker Button:hover {{
        background: {t['btn_hover']};
    }}
    #picker Button:focus {{
        text-style: bold;
    }}

    /* Modal: custom command */
    CustomCmdScreen {{ align: center middle; }}
    #cmd-box {{
        width: 70; height: auto; padding: 1 2;
        background: {t['panel_bg']}; border: round {t['border']};
    }}
    #cmd-title {{ color: {t['accent']}; text-style: bold; margin-bottom: 1; }}
    #cmd-help  {{ color: {t['fg_dim']}; margin-bottom: 1; }}
    #cmd-box Input {{
        background: {t['input_bg']};
        color: {t['fg']};
        border: round {t['input_border']};
    }}
    #cmd-box Input:focus {{
        border: round {t['accent']};
    }}

    /* Modal: theme picker */
    ThemePickerScreen {{ align: center middle; }}
    #theme-box {{
        width: 54; height: auto; padding: 1 2;
        background: {t['panel_bg']}; border: round {t['border']};
    }}
    #theme-title {{ color: {t['accent']}; text-style: bold; margin-bottom: 1; }}
    #theme-box RadioSet {{
        background: {t['panel_bg']};
        border: none;
        height: auto;
    }}
    #theme-box RadioButton {{
        background: {t['panel_bg']};
        color: {t['fg']};
        border: none;
        padding: 0 1;
    }}
    #theme-box RadioButton:hover {{
        background: {t['hover_bg']};
    }}
    #theme-box RadioButton.-on > .toggle--button {{
        color: {t['accent']};
    }}
    #theme-box Button {{
        margin-top: 1;
        background: {t['btn_bg']};
        color: {t['cursor_fg']};
        border: none;
    }}
    #theme-box Button:hover {{
        background: {t['btn_hover']};
    }}

    /* Modal: search cache */
    SearchCacheScreen {{ align: center middle; }}
    #search-box {{
        width: 80%; height: 80%; padding: 1 2;
        background: {t['panel_bg']}; border: round {t['border']};
    }}
    #search-title {{ color: {t['accent']}; text-style: bold; margin-bottom: 1; }}
    #search-help  {{ color: {t['fg_dim']}; margin-bottom: 1; }}
    #search-box Input {{
        background: {t['input_bg']};
        color: {t['fg']};
        border: round {t['input_border']};
        height: 3;
    }}
    #search-box Input:focus {{
        border: round {t['accent']};
    }}
    #search-options {{
        height: auto;
        padding: 0;
        margin: 1 0;
    }}
    #search-options Checkbox {{
        background: {t['panel_bg']};
        color: {t['fg']};
        border: none;
        padding: 0 1;
        margin-right: 2;
        height: 1;
    }}
    #search-options Checkbox:hover {{
        background: {t['hover_bg']};
    }}
    #search-options Checkbox.-on > .toggle--button {{
        color: {t['accent']};
    }}
    #search-buttons {{
        height: auto;
        margin-bottom: 1;
    }}
    #search-buttons Button {{
        background: {t['btn_bg']};
        color: {t['cursor_fg']};
        border: none;
        margin-right: 1;
    }}
    #search-buttons Button:hover {{
        background: {t['btn_hover']};
    }}
    #search-results {{
        height: 1fr;
        background: {t['panel_bg']};
        color: {t['fg']};
        border: round {t['accent_dark']};
        padding: 0 1;
        scrollbar-color: {t['border']};
        scrollbar-color-hover: {t['accent']};
        scrollbar-color-active: {t['accent']};
        scrollbar-background: {t['panel_bg']};
        scrollbar-background-hover: {t['panel_bg']};
        scrollbar-background-active: {t['panel_bg']};
        scrollbar-corner-color: {t['panel_bg']};
        scrollbar-size: 1 1;
    }}
    """


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
         desc="Parent-child tree of every process.\n\nHighlight a process and press 'd' to download its memory segment."),
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
         desc="Parent-child tree of every process.\n\nHighlight a process and press 'd' to download its memory segment."),
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
         desc="Parent-child process relationships.\n\nHighlight a process and press 'd' to download its memory segment."),
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


# Heuristics for detecting OS-mismatch errors from vol3 stderr.
_OS_MISMATCH_HINTS = (
    "no suitable",
    "unsatisfied",
    "could not satisfy",
    "no module",
    "symbols could not be found",
    "no compatible kernel",
    "not a valid",
    "couldn't find a suitable",
    "no symbols",
    "symbols.json",
    "isf",
)


def _looks_like_os_mismatch(plugin: str, err: str) -> bool:
    if not err:
        return False
    e = err.lower()
    if any(h in e for h in _OS_MISMATCH_HINTS):
        return True
    return False


def _os_mismatch_message(plugin: str, selected_os: str) -> str:
    return (
        f"This plugin ({plugin}) could not run against the loaded image.\n"
        f"You currently have OS = {selected_os.upper()} selected.\n\n"
        "This usually means the OS you picked does not match the memory dump.\n"
        "Quit qvi and re-launch (or use --fresh) to pick a different OS, or\n"
        "verify that the dump file really is from a "
        f"{selected_os} system."
    )


def run_plugin(dump: str, plugin: str, selected_os: str = "") -> tuple[bool, Any]:
    script = _vol_script(dump, plugin)
    try:
        p = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            **_POPEN_KW,
        )
        out, err = p.communicate()
        # Try to extract JSON
        for opener, closer in (("[", "]"), ("{", "}")):
            s, e = out.find(opener), out.rfind(closer)
            if s != -1 and e != -1:
                try:
                    parsed = json.loads(out[s:e + 1])
                    return True, parsed if isinstance(parsed, list) else [parsed]
                except json.JSONDecodeError:
                    pass
        # No JSON. Decide whether this looks like an OS mismatch.
        raw = (err.strip() or out.strip() or "No data returned.")
        if selected_os and _looks_like_os_mismatch(plugin, raw):
            friendly = _os_mismatch_message(plugin, selected_os)
            return False, friendly + "\n\n--- raw error ---\n" + raw
        return False, raw
    except Exception as ex:
        return False, str(ex)


def run_raw(dump: str, args_str: str, selected_os: str = "") -> str:
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
        text = (out or err or "(no output)").strip()
        # If only stderr came back AND it looks like an OS mismatch, prepend a hint.
        if (not out.strip()) and selected_os and _looks_like_os_mismatch(args_str, err):
            return (_os_mismatch_message(args_str.split()[0] if args_str else "?",
                                         selected_os)
                    + "\n\n--- raw error ---\n" + text)
        return text
    except subprocess.TimeoutExpired:
        return "Timed out after 300s."
    except Exception as ex:
        return str(ex)


def dump_segment(dump: str, pid: int | str, os_type: str) -> tuple[bool, str, list[Path]]:
    """
    Dump the memory segment of `pid` into HERE/dumped/pid_<pid>/.
    Returns (ok, message, list_of_files_written).
    """
    out_dir = HERE / DUMP_DIR_NAME / f"pid_{pid}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if os_type == "windows":
        plugin = "windows.memmap.Memmap"
    elif os_type == "linux":
        plugin = "linux.proc.Maps"
    elif os_type == "mac":
        plugin = "mac.proc_maps.Maps"
    else:
        plugin = "windows.memmap.Memmap"

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
        files = sorted(out_dir.glob("*"))
        if files:
            lines = "\n".join(
                f"  {f.name}  ({f.stat().st_size:,} B)" for f in files
            )
            return True, f"Saved to:\n  {out_dir}\n\n{lines}", files
        msg = err.strip() or out.strip() or "No files written."
        if _looks_like_os_mismatch(plugin, err):
            msg = _os_mismatch_message(plugin, os_type) + "\n\n--- raw error ---\n" + msg
        return False, msg, []
    except subprocess.TimeoutExpired:
        return False, "Timed out after 600s.", []
    except Exception as ex:
        return False, str(ex), []


def segment_already_dumped(pid: int | str) -> tuple[bool, list[Path]]:
    """
    Check if a memory segment for `pid` has already been dumped.
    Returns (exists, list_of_files).
    """
    out_dir = HERE / DUMP_DIR_NAME / f"pid_{pid}"
    if not out_dir.exists():
        return False, []
    files = sorted(out_dir.glob("*"))
    return (len(files) > 0), files


# ── pstree flattening ──────────────────────────────────────────────────────
def flatten_pstree(data: list[dict]) -> list[dict]:
    """
    Volatility3 pstree returns nested dicts where children live in
    '__children'. Flatten that into a list with a __depth annotation that
    correctly reflects tree position. Items without __children still get
    __depth=0.
    """
    if not data:
        return []

    out: list[dict] = []

    def walk(node: dict, depth: int) -> None:
        children = node.get("__children") or []
        # Copy without __children so the flattened row is clean.
        flat = {k: v for k, v in node.items() if k != "__children"}
        flat["__depth"] = depth
        out.append(flat)
        for ch in children:
            if isinstance(ch, dict):
                walk(ch, depth + 1)

    has_children_key = any(
        isinstance(item, dict) and "__children" in item for item in data
    )

    if has_children_key:
        for root in data:
            if isinstance(root, dict):
                walk(root, 0)
        return out

    # Fallback: build the tree ourselves from PID/PPID. Includes orphans so
    # nothing gets lost.
    return build_tree_from_flat(data)


def build_tree_from_flat(data: list[dict]) -> list[dict]:
    """
    Build a depth-annotated, parent-before-children list from a flat
    pslist-style array using PID and PPID. Handles orphans (PPID not in
    set) by promoting them to roots.
    """
    if not data:
        return []

    def get_pid(item: dict):
        return item.get("PID") if "PID" in item else item.get("Pid")

    def get_ppid(item: dict):
        return item.get("PPID") if "PPID" in item else item.get("Ppid")

    by_pid: dict = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = get_pid(item)
        if pid is None:
            continue
        # Use the first occurrence; vol3 occasionally returns dupes.
        if pid not in by_pid:
            by_pid[pid] = dict(item)

    children: dict = {}
    roots: list = []
    for pid, item in by_pid.items():
        ppid = get_ppid(item)
        # A node is a root if its parent is missing, is itself, or is 0.
        if ppid is None or ppid == pid or ppid == 0 or ppid not in by_pid:
            roots.append(pid)
        else:
            children.setdefault(ppid, []).append(pid)

    # Stable sort of children by PID for predictable ordering.
    for plist in children.values():
        plist.sort(key=lambda x: (x is None, x))
    roots.sort(key=lambda x: (x is None, x))

    out: list[dict] = []
    visited: set = set()

    def walk(pid, depth: int) -> None:
        if pid in visited:
            return
        visited.add(pid)
        node = dict(by_pid[pid])
        node["__depth"] = depth
        out.append(node)
        for child in children.get(pid, []):
            walk(child, depth + 1)

    for r in roots:
        walk(r, 0)

    # Anything still un-visited is part of a cycle; append it flat at depth 0
    # so the user still sees it.
    for pid in by_pid.keys():
        if pid not in visited:
            node = dict(by_pid[pid])
            node["__depth"] = 0
            out.append(node)
            visited.add(pid)

    return out


# ── Item label formatting ──────────────────────────────────────────────────
def make_label(item: dict) -> str:
    pid  = item.get("PID")  or item.get("Pid")
    name = (item.get("ImageFileName") or item.get("COMM") or item.get("Name") or
            item.get("Process") or item.get("Module") or "")
    depth = item.get("__depth", 0)
    ind   = ("  " * depth + "|- ") if depth else ""

    if item.get("User") and item.get("NTLM"):
        return f"{item['User']}  -  NTLM: {item['NTLM'][:16]}..."
    if item.get("Args") and name:
        return f"{ind}[{pid}] {name}  >  {str(item['Args'])[:30]}"
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


# ── Modal: OS picker ───────────────────────────────────────────────────────
class OSPickerScreen(ModalScreen[str]):
    """OS selector. Shown unconditionally on startup -- user picks which OS
    the dump is from. No auto-detection."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="picker"):
            yield Static("Select OS for memory image", id="picker-title")
            yield Static(
                "Pick the operating system this dump came from. "
                "If you pick the wrong one, plugins will fail with a hint.",
                id="picker-sub",
            )
            yield RadioSet(
                RadioButton("Windows", value=True, id="os-windows"),
                RadioButton("Linux",            id="os-linux"),
                RadioButton("macOS",            id="os-mac"),
            )
            yield Button("Confirm", id="picker-confirm", variant="primary")

    def on_mount(self) -> None:
        try:
            self.query_one("#picker-confirm", Button).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "picker-confirm":
            self._submit()

    def _submit(self) -> None:
        rs = self.query_one(RadioSet)
        if rs.pressed_button is None:
            self.dismiss("windows")
            return
        mapping = {"os-windows": "windows", "os-linux": "linux", "os-mac": "mac"}
        self.dismiss(mapping.get(rs.pressed_button.id, "windows"))

    def action_cancel(self) -> None:
        # Cancel still picks something so the app can boot. Default = windows.
        self.dismiss("windows")


# ── Modal: theme picker ────────────────────────────────────────────────────
class ThemePickerScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, current: str) -> None:
        super().__init__()
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-box"):
            yield Static("Select color theme", id="theme-title")
            buttons = []
            for name in THEME_ORDER:
                buttons.append(
                    RadioButton(
                        THEMES[name]["label"],
                        value=(name == self.current),
                        id=f"theme-{name}",
                    )
                )
            yield RadioSet(*buttons)
            yield Button("Apply", id="theme-apply", variant="primary")

    def on_mount(self) -> None:
        try:
            self.query_one("#theme-apply", Button).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "theme-apply":
            rs = self.query_one(RadioSet)
            if rs.pressed_button is None:
                self.dismiss(None)
                return
            btn_id = rs.pressed_button.id or ""
            name = btn_id.removeprefix("theme-")
            if name in THEMES:
                self.dismiss(name)
            else:
                self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Modal: custom command input ───────────────────────────────────────────
class CustomCmdScreen(ModalScreen[str | None]):
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


# ── Modal: search cache ────────────────────────────────────────────────────
class SearchCacheScreen(ModalScreen[None]):
    """
    Substring search across the cached vol3 output. Each cached plugin's
    list of entries is iterated; entries whose JSON serialization contains
    the query are returned in full. Results are written into a scrollable
    RichLog inside the modal AND copied to the app's right-side detail pane
    when the modal closes.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("ctrl+enter", "run", "Run", show=False),
    ]

    def __init__(self, cache: dict) -> None:
        super().__init__()
        self.cache = cache
        self.last_results_text: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Static("Search cached output", id="search-title")
            yield Static(
                "Type a query and press Run. Matches whole entries from the "
                "cached JSON. Use the toggles below for case sensitivity / "
                "inverted match (exclude rather than include).",
                id="search-help",
            )
            yield Input(placeholder="search query (e.g. notepad.exe)",
                        id="search-input")
            with Horizontal(id="search-options"):
                yield Checkbox("Case sensitive", value=False, id="opt-case")
                yield Checkbox("Inverted match", value=False, id="opt-invert")
            with Horizontal(id="search-buttons"):
                yield Button("Run", id="search-run", variant="primary")
                yield Button("Close", id="search-close")
            yield RichLog(id="search-results", markup=True, wrap=True,
                          highlight=False, auto_scroll=False)

    def on_mount(self) -> None:
        try:
            self.query_one("#search-input", Input).focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self._run_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-run":
            self._run_search()
        elif event.button.id == "search-close":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_run(self) -> None:
        self._run_search()

    def _run_search(self) -> None:
        query = self.query_one("#search-input", Input).value
        case_sensitive = self.query_one("#opt-case", Checkbox).value
        invert = self.query_one("#opt-invert", Checkbox).value

        log = self.query_one("#search-results", RichLog)
        log.clear()

        if not query:
            log.write("[bold]No query specified.[/]")
            return

        needle = query if case_sensitive else query.lower()

        match_count = 0
        plugins_with_hits = 0
        rendered: list[str] = []

        for plugin_id, entries in self.cache.items():
            if plugin_id.startswith("__"):
                continue
            if not isinstance(entries, list):
                continue
            hits_in_plugin: list[dict] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                try:
                    blob = json.dumps(entry, default=str, ensure_ascii=False)
                except Exception:
                    blob = str(entry)
                hay = blob if case_sensitive else blob.lower()
                contains = needle in hay
                hit = (not contains) if invert else contains
                if hit:
                    hits_in_plugin.append(entry)

            if hits_in_plugin:
                plugins_with_hits += 1
                match_count += len(hits_in_plugin)
                plugin_label = PLUGIN_BY_ID.get(plugin_id, {}).get(
                    "label", plugin_id
                )
                rendered.append(f"[bold]== {_markup_escape(plugin_label)} "
                                f"({_markup_escape(plugin_id)}) "
                                f"-- {len(hits_in_plugin)} match"
                                f"{'es' if len(hits_in_plugin) != 1 else ''} ==[/]")
                rendered.append("")
                for entry in hits_in_plugin:
                    try:
                        pretty = json.dumps(entry, indent=2, default=str,
                                            ensure_ascii=False)
                    except Exception:
                        pretty = str(entry)
                    # JSON content may contain '[' / ']' which would otherwise
                    # be eaten by Rich's markup parser. Escape it.
                    rendered.append(_markup_escape(pretty))
                    rendered.append("")

        header_mode = "exclude" if invert else "include"
        header_case = "case-sensitive" if case_sensitive else "case-insensitive"
        log.write(
            f"[bold]Search:[/] {_markup_escape(repr(query))}  "
            f"[dim]({header_mode}, {header_case})[/]"
        )
        log.write(
            f"[bold]Found {match_count} matching entr"
            f"{'y' if match_count == 1 else 'ies'} "
            f"across {plugins_with_hits} plugin"
            f"{'' if plugins_with_hits == 1 else 's'}.[/]"
        )
        log.write("")

        if not rendered:
            log.write("[dim](no entries matched)[/]")
        else:
            for chunk in rendered:
                log.write(chunk)

        # Save the full results so the app can mirror them into the
        # main detail pane when the modal closes. The text is markup-safe:
        # JSON content is already escaped above, summary lines are escaped
        # here, and plugin section headers use [bold]...[/] which we leave
        # intact so they render with emphasis in the detail pane too.
        full_lines = [
            f"Search: {_markup_escape(repr(query))} "
            f"({header_mode}, {header_case})",
            (f"Found {match_count} matching entries across "
             f"{plugins_with_hits} plugins."),
            "",
        ]
        full_lines.extend(rendered)
        self.last_results_text = "\n".join(full_lines)


# ── Main App ───────────────────────────────────────────────────────────────
class QviApp(App):
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("up,k",        "nav_up",        "Up"),
        Binding("down,j",      "nav_down",      "Down"),
        Binding("right,enter", "open",          "Open"),
        Binding("left,escape", "back",          "Back"),
        Binding("d",           "download",      "Dump"),
        Binding("r",           "run_custom",    "Cmd"),
        Binding("c",           "copy_detail",   "Copy"),
        Binding("f",           "search_cache",  "Search"),
        Binding("R",           "refresh_run",   "Re-run"),
        Binding("/",           "focus_filter",  "Filter"),
        Binding("t",           "pick_theme",    "Theme"),
        Binding("q,ctrl+c",    "quit",          "Quit"),
    ]

    status_text = reactive("")

    def __init__(self, dump: str, cache: dict, selected_os: str) -> None:
        super().__init__()
        self.theme_name = load_theme_name()
        # Provide the CSS up front -- App reads `CSS` in its constructor on
        # some Textual versions, so set both attribute and class-level.
        self.CSS = build_css(THEMES[self.theme_name])

        self.dump        = dump
        self.cache       = cache
        # `selected_os` may be empty -- that means we still need to ask.
        self.detected_os = selected_os

        self.level: str       = "root"   # "root" or plugin id
        self.vis_plugins      = plugins_for_os(selected_os) if selected_os else []
        self.root_rows: list[dict] = []  # [{plugin: dict, cached: bool}]
        self.result_data: list[dict] = []        # full unfiltered data
        self.filtered_data: list[dict] = []      # what's actually in the table
        self.result_plugin: dict | None = None
        self.list_sel = 0
        self._busy = False
        self._filter_text = ""

        # Background-fetched dump metadata (hostname, system time).
        self.host_name: str = ""
        self.dump_time: str = ""

    # ── compose ────────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Container(id="topbar"):
            yield Static(self._topbar_text(), id="topbar-content", markup=True)

        with Horizontal(id="main"):
            with Vertical(id="left-panel"):
                with Container(id="filter-bar"):
                    yield Input(
                        placeholder="filter (press / to focus, Enter to apply)",
                        id="filter-input",
                    )
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

    # ── theming ───────────────────────────────────────────────────────────
    def _t(self) -> dict:
        return THEMES[self.theme_name]

    def _apply_theme(self, name: str) -> None:
        if name not in THEMES:
            return
        self.theme_name = name
        save_theme_name(name)
        # Replace the active stylesheet. Textual exposes stylesheet management
        # through the screen's stylesheet object; the cleanest cross-version
        # path is to re-set CSS and trigger a refresh.
        try:
            self.stylesheet.parse(build_css(self._t()))
            self.stylesheet.reparse()
            self.refresh(layout=True)
            self.screen.refresh(layout=True)
        except Exception:
            # Fallback: re-set the class-level CSS string and ask textual to
            # reload. Some versions need a full screen refresh to pick this up.
            self.CSS = build_css(self._t())
            try:
                self.refresh(layout=True)
            except Exception:
                pass

        # Re-render anything that contains theme-coloured rich markup.
        try:
            self._refresh_topbar()
        except Exception:
            pass
        try:
            if self.level == "root":
                self._update_detail_root()
                self._update_bottom_help()
            else:
                self._update_detail_result()
        except Exception:
            pass

    # ── header text ────────────────────────────────────────────────────────
    def _topbar_text(self) -> str:
        t = self._t()
        os_label = OS_LABELS.get(self.detected_os, "?")
        name = _markup_escape(Path(self.dump).name)
        cached_count = sum(1 for p in self.vis_plugins if p["id"] in self.cache)
        sep = f"[{t['accent_dark']}] | [/]"
        status = _markup_escape(self.status_text or "ready")
        status_color = t['warn'] if self.status_text else t['ok']
        host = _markup_escape(self.host_name or "?")
        dtime = _markup_escape(self.dump_time or "?")
        return (
            f"[{t['accent']}]OS:[/] [{t['fg']}]{os_label}[/]  "
            f"{sep}  [{t['accent']}]Image:[/] [{t['fg']}]{name}[/]  "
            f"{sep}  [{t['accent']}]Host:[/] [{t['fg']}]{host}[/]  "
            f"{sep}  [{t['accent']}]Dump time:[/] [{t['fg']}]{dtime}[/]  "
            f"{sep}  [{t['accent']}]Plugins:[/] [{t['fg']}]{len(self.vis_plugins)}[/]  "
            f"{sep}  [{t['accent']}]Cached:[/] [{t['warn']}]{cached_count}[/]  "
            f"{sep}  [{status_color}]{status}[/]"
        )

    def _refresh_topbar(self) -> None:
        try:
            self.query_one("#topbar-content", Static).update(self._topbar_text())
        except Exception:
            pass

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

        # Pre-populate dump_time from file mtime as a sane fallback.
        try:
            mtime = Path(self.dump).stat().st_mtime
            self.dump_time = _dt.datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            pass

        if self.detected_os:
            self._after_os_picked()
        else:
            # Always prompt the user to pick the OS -- no auto-detection.
            self.push_screen(OSPickerScreen(), self._on_os_picked)

    def _on_os_picked(self, os_type: str | None) -> None:
        self._set_os(os_type or "windows")
        self._after_os_picked()

    def _after_os_picked(self) -> None:
        self._build_root_table()
        self._update_detail_root()
        self._refresh_topbar()
        # Move focus off the filter Input so app-level keybinds (t, f, /, ...)
        # work immediately. The filter is only focused when the user presses /.
        try:
            self.query_one("#plugin-table", DataTable).focus()
        except Exception:
            pass
        # Best-effort metadata fetch in the background so the topbar updates.
        threading.Thread(target=self._fetch_metadata, daemon=True).start()

    def _set_os(self, os_type: str) -> None:
        self.detected_os = os_type
        self.cache["__os__"] = os_type
        save_cache(self.dump, self.cache)
        self.vis_plugins = plugins_for_os(os_type)
        self.status_text = ""
        self._refresh_topbar()

    # ── metadata (hostname / dump time) ───────────────────────────────────
    def _fetch_metadata(self) -> None:
        """Run a small vol3 plugin to pull hostname / system time. Best
        effort -- if it fails we just leave the topbar fields as '?'."""
        host = ""
        dtime = ""

        if self.detected_os == "windows":
            # windows.info gives us SystemTime and NtSystemRoot, but not the
            # hostname directly. Hostname comes from registry; envars also
            # exposes COMPUTERNAME per process and is much faster.
            ok, data = run_plugin(self.dump, "windows.info", self.detected_os)
            if ok and isinstance(data, list):
                for row in data:
                    if not isinstance(row, dict):
                        continue
                    val = row.get("Value")
                    key = (row.get("Variable") or "").lower()
                    if "systemtime" in key and val:
                        dtime = str(val)
                    elif "ntsystemroot" in key and val and not host:
                        # Not a hostname, but better than nothing as a fallback
                        pass

            # Try envars for COMPUTERNAME -- this is only run if cheap enough.
            try:
                ok2, data2 = run_plugin(self.dump, "windows.envars",
                                        self.detected_os)
                if ok2 and isinstance(data2, list):
                    for row in data2:
                        if not isinstance(row, dict):
                            continue
                        var = (row.get("Variable") or "").upper()
                        if var == "COMPUTERNAME":
                            host = str(row.get("Value") or "")
                            break
            except Exception:
                pass

        elif self.detected_os == "linux":
            ok, data = run_plugin(self.dump, "linux.banner", self.detected_os)
            if ok and isinstance(data, list) and data:
                # Banner gives kernel info; hostname is rarely there but try.
                first = data[0]
                if isinstance(first, dict):
                    banner = (first.get("Banner") or "").strip()
                    if banner:
                        # Try to spot something that looks like a hostname.
                        for tok in banner.split():
                            if "@" in tok:
                                host = tok.split("@", 1)[1]
                                break

        elif self.detected_os == "mac":
            # Mac has fewer reliable hostname sources. Skip.
            pass

        # Push back to the UI thread.
        def update():
            if host:
                self.host_name = host
            if dtime:
                self.dump_time = dtime
            self._refresh_topbar()
        try:
            self.call_from_thread(update)
        except Exception:
            pass

    # ── building tables ───────────────────────────────────────────────────
    def _build_root_table(self) -> None:
        table: DataTable = self.query_one("#plugin-table", DataTable)
        table.clear(columns=True)
        t = self._t()
        table.add_columns("  ", "Name", "Plugin", "Cached")
        self.root_rows = []
        for p in self.vis_plugins:
            cached = p["id"] in self.cache
            dot = Text("*", style=t['ok'] if cached else t['fg_faint'])
            table.add_row(
                dot,
                Text(p["label"], style=t['fg']),
                Text(p["plugin"], style=t['fg_dim']),
                Text("yes" if cached else "", style=t['warn']),
            )
            self.root_rows.append({"plugin": p, "cached": cached})

        table.cursor_type = "row"
        if self.root_rows:
            table.move_cursor(row=0)
            self.list_sel = 0

    def _build_results_table(self) -> None:
        table: DataTable = self.query_one("#plugin-table", DataTable)
        table.clear(columns=True)
        t = self._t()

        if not self.filtered_data:
            table.add_columns("info")
            if self._filter_text and self.result_data:
                table.add_row(Text(
                    f"(no rows match filter '{self._filter_text}')",
                    style=t['fg_dim'],
                ))
            else:
                table.add_row(Text("(no rows returned)", style=t['fg_dim']))
            return

        # Pick at most 6 useful columns from the first item's keys
        first = self.filtered_data[0]
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

        table.add_columns(*[Text(k, style=f"{t['accent']} bold") for k in keys])
        for item in self.filtered_data:
            cells = []
            for k in keys:
                v = item.get(k, "")
                s = str(v)
                if len(s) > 50:
                    s = s[:47] + "..."
                # Indent first column for tree depth
                if k == keys[0] and "__depth" in item and item["__depth"]:
                    s = "  " * item["__depth"] + s
                cells.append(Text(s, style=t['fg']))
            table.add_row(*cells)

        table.cursor_type = "row"
        table.move_cursor(row=0)
        self.list_sel = 0

    # ── filtering ─────────────────────────────────────────────────────────
    def _apply_filter(self) -> None:
        """Rebuild filtered_data from result_data based on self._filter_text."""
        if not self._filter_text:
            self.filtered_data = list(self.result_data)
        else:
            needle = self._filter_text.lower()
            kept: list[dict] = []
            for item in self.result_data:
                # Concatenate all string-able fields and search.
                blob_parts = []
                for k, v in item.items():
                    if k.startswith("__"):
                        continue
                    try:
                        blob_parts.append(str(v))
                    except Exception:
                        pass
                blob = " ".join(blob_parts).lower()
                if needle in blob:
                    kept.append(item)
            self.filtered_data = kept

    # ── detail pane ───────────────────────────────────────────────────────
    def _detail(self) -> RichLog:
        return self.query_one("#detail-log", RichLog)

    def _bottom(self) -> RichLog:
        return self.query_one("#bottom-log", RichLog)

    def _update_detail_root(self) -> None:
        log = self._detail()
        log.clear()
        t = self._t()
        if not self.root_rows or self.list_sel >= len(self.root_rows):
            return
        row = self.root_rows[self.list_sel]
        if row["plugin"] is None:
            log.write(f"[{t['fg_dim']}]section header[/]")
            return
        cat = row["plugin"]
        log.write(f"[{t['accent']} bold]{cat['label']}[/]")
        log.write("")
        log.write(f"[{t['accent']}]Plugin[/]   [{t['fg']}]{cat['plugin']}[/]")
        log.write("")
        for line in cat["desc"].split("\n"):
            log.write(f"[{t['fg']}]{line}[/]")
        if row["cached"]:
            log.write("")
            log.write(f"[{t['warn']}]* Cached[/]  [{t['fg_dim']}]results available instantly[/]")
            log.write(f"[{t['fg_dim']}]press R to re-run[/]")
        log.write("")
        log.write(f"[{t['accent']} bold]> press Enter / Right to run[/]")

    def _update_detail_result(self) -> None:
        log = self._detail()
        log.clear()
        t = self._t()
        if not self.filtered_data or self.list_sel >= len(self.filtered_data):
            log.write(f"[{t['fg_dim']}](nothing selected)[/]")
            return
        item = self.filtered_data[self.list_sel]
        is_tree = (self.result_plugin
                   and "pstree" in self.result_plugin["plugin"])

        name = (item.get("ImageFileName") or item.get("COMM")
                or item.get("Name") or "item")
        pid = item.get("PID") or item.get("Pid") or ""

        title = f"{name}  [{pid}]" if pid else str(name)
        log.write(f"[{t['accent']} bold]{_markup_escape(title)}[/]")
        log.write("")

        for k, v in item.items():
            if k.startswith("__") or k in ("Offset", "TreeDepth"):
                continue
            sval = str(v)
            if len(sval) > 200:
                sval = sval[:197] + "..."
            # User data may contain '[' / ']' that would otherwise be
            # interpreted as Rich markup tags.
            log.write(
                f"[{t['accent']}]{_markup_escape(str(k)):<18}[/] "
                f"[{t['fg']}]{_markup_escape(sval)}[/]"
            )

        if pid:
            log.write("")
            log.write(f"[{t['accent_dark']}]" + ("-" * 40) + "[/]")
            log.write(f"[{t['accent']} bold]Download Memory Segment[/]")
            log.write(f"[{t['fg']}]Press 'd' to dump PID {pid}[/]")
            log.write(f"[{t['fg_dim']}]Output: {DUMP_DIR_NAME}/pid_{pid}/[/]")

    def _update_bottom_help(self) -> None:
        b = self._bottom()
        b.clear()
        t = self._t()
        b.write(f"[{t['accent']} bold]Raw output / log[/]")
        b.write(f"[{t['fg_dim']}]Plugin output, status messages, and dump notifications appear here.[/]")
        b.write("")
        b.write(f"[{t['fg_dim']}]Image:[/] [{t['fg']}]{_markup_escape(str(self.dump))}[/]")
        b.write(f"[{t['fg_dim']}]Cache:[/] [{t['fg']}]{_markup_escape(str(_cache_path(self.dump)))}[/]")
        b.write(f"[{t['fg_dim']}]Dumps:[/] [{t['fg']}]{_markup_escape(str(HERE / DUMP_DIR_NAME))}[/]")

    def _bottom_log(self, *lines: str) -> None:
        b = self._bottom()
        b.clear()
        for ln in lines:
            b.write(ln)

    def _bottom_append(self, *lines: str) -> None:
        b = self._bottom()
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
            self.list_sel = idx
            self._update_detail_root()
        else:
            self.list_sel = idx
            self._update_detail_result()

    def on_data_table_row_selected(self,
                                   event: DataTable.RowSelected) -> None:
        # Enter / double-click on a row
        self.action_open()

    # ── filter input handling ─────────────────────────────────────────────
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            self._filter_text = event.value.strip()
            self._apply_filter()
            if self.level == "root":
                # Filtering at root: just narrow which plugin rows are shown.
                self._build_root_table_filtered()
            else:
                self._build_results_table()
                self._update_detail_result()
            # Hand focus back to the table so j/k work again.
            try:
                self.query_one("#plugin-table", DataTable).focus()
            except Exception:
                pass

    def _build_root_table_filtered(self) -> None:
        table: DataTable = self.query_one("#plugin-table", DataTable)
        table.clear(columns=True)
        t = self._t()
        table.add_columns("  ", "Name", "Plugin", "Cached")
        self.root_rows = []
        needle = self._filter_text.lower()
        for p in self.vis_plugins:
            if needle and (needle not in p["label"].lower()
                           and needle not in p["plugin"].lower()):
                continue
            cached = p["id"] in self.cache
            dot = Text("*", style=t['ok'] if cached else t['fg_faint'])
            table.add_row(
                dot,
                Text(p["label"], style=t['fg']),
                Text(p["plugin"], style=t['fg_dim']),
                Text("yes" if cached else "", style=t['warn']),
            )
            self.root_rows.append({"plugin": p, "cached": cached})

        table.cursor_type = "row"
        if self.root_rows:
            table.move_cursor(row=0)
            self.list_sel = 0

    # ── actions ───────────────────────────────────────────────────────────
    def action_focus_filter(self) -> None:
        try:
            self.query_one("#filter-input", Input).focus()
        except Exception:
            pass

    def action_pick_theme(self) -> None:
        if self._busy: return
        def cb(name: str | None) -> None:
            if name:
                self._apply_theme(name)
                self.status_text = f"theme: {THEMES[name]['label']}"
                self.set_timer(2.0, lambda: setattr(self, "status_text", ""))
        self.push_screen(ThemePickerScreen(self.theme_name), cb)

    def action_search_cache(self) -> None:
        if self._busy: return
        if not self.cache or all(k.startswith("__") for k in self.cache.keys()):
            self._bottom_log(
                f"[{self._t()['warn']} bold]Nothing cached yet[/]",
                f"[{self._t()['fg_dim']}]Run at least one plugin before searching the cache.[/]",
            )
            return

        def cb(_: None) -> None:
            # When the modal closes, mirror its results into the right pane
            # so the user can keep scrolling them.
            try:
                screen = self._last_search_screen
                text = getattr(screen, "last_results_text", "")
            except Exception:
                text = ""
            if text:
                log = self._detail()
                log.clear()
                t = self._t()
                log.write(f"[{t['accent']} bold]Cache search results[/]")
                log.write("")
                for line in text.split("\n"):
                    log.write(line)
                self._bottom_log(
                    f"[{t['ok']}]Search complete[/]  "
                    f"[{t['fg_dim']}]results mirrored to detail pane[/]",
                )

        screen = SearchCacheScreen(self.cache)
        self._last_search_screen = screen
        self.push_screen(screen, cb)

    def action_nav_up(self) -> None:
        if self._busy: return
        table: DataTable = self.query_one("#plugin-table", DataTable)
        if self.level == "root":
            idx = max(0, self.list_sel - 1)
            table.move_cursor(row=idx)
        else:
            idx = max(0, self.list_sel - 1)
            table.move_cursor(row=idx)

    def action_nav_down(self) -> None:
        if self._busy: return
        table: DataTable = self.query_one("#plugin-table", DataTable)
        if self.level == "root":
            n = len(self.root_rows)
            if n == 0: return
            idx = min(n - 1, self.list_sel + 1)
            table.move_cursor(row=idx)
        else:
            n = len(self.filtered_data)
            if n == 0: return
            idx = min(n - 1, self.list_sel + 1)
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
            # In any module: Enter does nothing destructive. Use 'd' to dump.
            self._update_detail_result()

    def action_back(self) -> None:
        if self._busy: return
        if self.level == "root":
            return
        self.level = "root"
        self.result_data = []
        self.filtered_data = []
        self.result_plugin = None
        self.list_sel = 0
        self._filter_text = ""
        try:
            self.query_one("#filter-input", Input).value = ""
        except Exception:
            pass
        self._build_root_table()
        self._update_detail_root()
        self._update_bottom_help()
        self._refresh_topbar()

    def action_download(self) -> None:
        """
        Dump the memory segment of the currently-highlighted process. Works
        in any module that has a PID column. If no PID is present, log it
        and bail out gracefully.
        """
        if self._busy: return
        if self.level == "root": return
        if not self.filtered_data: return
        if self.list_sel >= len(self.filtered_data): return

        item = self.filtered_data[self.list_sel]
        pid = item.get("PID") or item.get("Pid")
        if not pid:
            self._bottom_log(
                f"[{self._t()['warn']} bold]No PID on this row[/]",
                f"[{self._t()['fg_dim']}]Memory dump only works on rows that have a PID column.[/]",
            )
            return

        # Idempotency check -- don't redump if the directory already has files.
        already, files = segment_already_dumped(pid)
        if already:
            t = self._t()
            self._bottom_log(
                f"[{t['warn']} bold]Already dumped -- PID {pid}[/]",
                f"[{t['fg_dim']}]Skipping. Existing files in {DUMP_DIR_NAME}/pid_{pid}/:[/]",
            )
            for f in files[:30]:
                self._bottom_append(
                    f"[{t['fg']}]  {_markup_escape(f.name)}  "
                    f"({f.stat().st_size:,} B)[/]"
                )
            if len(files) > 30:
                self._bottom_append(
                    f"[{t['fg_dim']}]  ... and {len(files) - 30} more[/]"
                )
            return

        self._download_segment(pid)

    def action_run_custom(self) -> None:
        if self._busy: return
        def cb(args: str | None) -> None:
            if not args: return
            self._busy = True
            self.status_text = f"running: {args}"
            t = self._t()
            self._bottom_log(
                f"[{t['accent']} bold]$ {_markup_escape(args)}[/]",
                f"[{t['fg_dim']}]running...[/]",
            )

            def worker():
                out = run_raw(self.dump, args, self.detected_os)
                self.call_from_thread(self._custom_done, args, out)
            threading.Thread(target=worker, daemon=True).start()

        self.push_screen(CustomCmdScreen(), cb)

    def _custom_done(self, args: str, out: str) -> None:
        self._busy = False
        self.status_text = ""
        b = self._bottom()
        b.clear()
        t = self._t()
        b.write(f"[{t['accent']} bold]$ {_markup_escape(args)}[/]")
        b.write("")
        for line in out[:8000].split("\n"):
            b.write(f"[{t['fg']}]{_markup_escape(line)}[/]")

    def action_copy_detail(self) -> None:
        # Best-effort clipboard copy. Falls back gracefully.
        try:
            log = self._detail()
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
        if self.level == "root":
            if self.list_sel >= len(self.root_rows): return
            cat = self.root_rows[self.list_sel]["plugin"]
            if cat is None or cat["plugin"] == "__custom__": return
            if cat["id"] in self.cache:
                del self.cache[cat["id"]]
                save_cache(self.dump, self.cache)
            self._load_plugin(cat)
        else:
            # Re-run the current module
            if not self.result_plugin: return
            cat = self.result_plugin
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
        t = self._t()

        log = self._detail()
        log.clear()
        log.write(f"[{t['accent']} bold]Running {cat['label']}[/]")
        log.write("")
        log.write(f"[{t['fg']}]Plugin:  {cat['plugin']}[/]")
        log.write(f"[{t['fg']}]Image:   {Path(self.dump).name}[/]")
        log.write("")
        log.write(f"[{t['warn']}]Working...[/] [{t['fg_dim']}]vol3 may take 30 s to several minutes.[/]")
        log.write(f"[{t['fg_dim']}]The first plugin is the slowest because vol3 builds its symbol cache.[/]")

        self._bottom_log(
            f"[{t['accent']} bold]Running {cat['plugin']}[/]",
            f"[{t['fg_dim']}]This may take a few minutes...[/]",
        )

        def worker():
            ok, data = run_plugin(self.dump, cat["plugin"], self.detected_os)
            self.call_from_thread(self._plugin_done, cat, ok, data)

        threading.Thread(target=worker, daemon=True).start()

    def _plugin_done(self, cat: dict, ok: bool, data: Any) -> None:
        self._busy = False
        self.status_text = ""
        t = self._t()
        if ok:
            self.cache[cat["id"]] = data
            save_cache(self.dump, self.cache)
            self._show_results(cat, data)
            self._bottom_log(
                f"[{t['ok']}]Done[/]  [{t['fg']}]{cat['plugin']}[/] -> "
                f"[{t['fg']}]{len(data)} rows[/]"
            )
        else:
            self._detail().clear()
            self._detail().write(f"[{t['accent']} bold]Error[/]")
            self._detail().write("")
            for ln in str(data)[:4000].split("\n"):
                self._detail().write(f"[{t['fg']}]{_markup_escape(ln)}[/]")
            self._detail().write("")
            self._detail().write(f"[{t['fg_dim']}]press Left/Esc to go back[/]")
            self._bottom_log(
                f"[{t['accent']}]Error:[/] [{t['fg']}]"
                f"{_markup_escape(str(data)[:300])}[/]"
            )

    def _show_results(self, cat: dict, data: list[dict]) -> None:
        if "pstree" in cat["plugin"]:
            data = flatten_pstree(data)
            # Persist the flattened version so future runs are correct.
            self.cache[cat["id"]] = data
            save_cache(self.dump, self.cache)

        self.level = cat["id"]
        self.result_data = data
        self._filter_text = ""
        try:
            self.query_one("#filter-input", Input).value = ""
        except Exception:
            pass
        self._apply_filter()
        self.result_plugin = cat
        self.list_sel = 0
        self._build_results_table()
        self._update_detail_result()
        self._refresh_topbar()

    # ── segment download ─────────────────────────────────────────────────
    def _download_segment(self, pid: int | str) -> None:
        self._busy = True
        self.status_text = f"dumping pid {pid}"
        t = self._t()
        self._bottom_log(
            f"[{t['accent']} bold]Downloading memory segment for PID {pid}[/]",
            f"[{t['fg_dim']}]This may take several minutes...[/]",
        )

        def worker():
            ok, msg, files = dump_segment(self.dump, pid, self.detected_os)
            self.call_from_thread(self._download_done, pid, ok, msg, files)

        threading.Thread(target=worker, daemon=True).start()

    def _download_done(self, pid, ok: bool, msg: str, files: list[Path]) -> None:
        self._busy = False
        self.status_text = ""
        b = self._bottom()
        b.clear()
        t = self._t()
        if ok:
            b.write(f"[{t['ok']} bold]Saved memory segment -- PID {pid}[/]")
        else:
            b.write(f"[{t['accent']} bold]Segment dump FAILED -- PID {pid}[/]")
        b.write("")
        for line in str(msg).split("\n"):
            b.write(f"[{t['fg']}]{_markup_escape(line)}[/]")


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
    # When --fresh is used we drop any saved OS so the picker is shown again.
    selected_os = "" if fresh else cache.get("__os__", "")

    app = QviApp(dump, cache, selected_os)
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
