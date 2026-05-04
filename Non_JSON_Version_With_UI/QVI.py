import os
import sys
import subprocess
import json
import urllib.request
import zipfile
import traceback
from pathlib import Path

# ============================================================================
# 1. BOOTSTRAPPER & DEPENDENCY MANAGER 
# ============================================================================
def setup_dependencies():
    """Ensures ALL core and advanced Volatility 3 dependencies are installed."""
    
    dependencies = {
        "textual": "textual",
        "volatility3": "volatility3",
        "pefile": "pefile",             
        "capstone": "capstone",         
        "yara": "yara-python",          
        "jsonschema": "jsonschema",     
        "Crypto": "pycryptodome"        
    }
    
    packages_needed =[]
    
    for mod_name, pip_name in dependencies.items():
        try:
            __import__(mod_name)
        except ImportError:
            packages_needed.append(pip_name)
            
    if packages_needed:
        print(f"[*] Missing advanced libraries detected. Auto-installing: {', '.join(packages_needed)}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *packages_needed])
            print("[+] Dependencies installed successfully!")
            print("[*] Restarting script to apply changes...")
            subprocess.call([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception as e:
            print(f"\n[!] ERROR installing dependencies: {e}")
            input("Press Enter to exit...")
            sys.exit(1)

    cache_dir = Path.home() / ".cache" / "volatility3" / "symbols"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    symbol_urls = {
        "windows.zip": "https://downloads.volatilityfoundation.org/volatility3/symbols/windows.zip",
        "linux.zip": "https://downloads.volatilityfoundation.org/volatility3/symbols/linux.zip",
        "mac.zip": "https://downloads.volatilityfoundation.org/volatility3/symbols/mac.zip"
    }
    
    for file_name, url in symbol_urls.items():
        zip_path = cache_dir / file_name
        if not zip_path.exists():
            print(f"\n[*] Downloading {file_name} for offline forensic analysis...")
            try:
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(cache_dir)
                print(f"[+] {file_name} downloaded successfully!")
            except Exception as e:
                print(f"[-] Warning: Failed to download {file_name}. Continuing...")

setup_dependencies()

# ============================================================================
# 2. APPLICATION LOGIC & TUI
# ============================================================================
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import OptionList, Header, Footer, Markdown
from textual.widgets.option_list import Option
from textual import work, on

CATEGORIES =[
    {"header": True, "label": "=== WINDOWS ==="},
    {"id": "w_info", "label": " |- OS & System Info", "plugin": "windows.info", "desc": "Extracts core OS architecture, version, and kernel base."},
    {"id": "w_pslist", "label": " |- Processes (pslist)", "plugin": "windows.pslist", "desc": "Analyzes memory to find all currently running programs."},
    {"id": "w_pstree", "label": " |- Process Tree (pstree)", "plugin": "windows.pstree", "desc": "Shows parent-child process tree. \n\n*(Note: Shows fewer processes than pslist if malware has unlinked itself or orphaned processes exist.)*"},
    {"id": "w_cmdline", "label": " |- Command Lines", "plugin": "windows.cmdline", "desc": "Extracts the exact command line arguments used to launch processes."},
    {"id": "w_netscan", "label": " |- Network Connections", "plugin": "windows.netscan", "desc": "Scans memory for open network sockets and active connections."},
    {"id": "w_malfind", "label": " |- Malfind (Injected Code)", "plugin": "windows.malfind", "desc": "Finds hidden, injected, or unpacked executable code in process memory."},
    {"id": "w_hashdump", "label": " |- Password Hashes", "plugin": "windows.hashdump", "desc": "Extracts NTLM user password hashes from the registry in memory."},
    {"id": "w_filescan", "label": " |- File Scanner", "plugin": "windows.filescan", "desc": "Finds files that were open or cached in memory at the time of the dump."},

    {"header": True, "label": ""}, 
    {"header": True, "label": "=== LINUX ==="},
    {"id": "l_info", "label": " |- OS Info (banner)", "plugin": "linux.banner", "desc": "Extracts the Linux banner and kernel version."},
    {"id": "l_pslist", "label": " |- Processes (pslist)", "plugin": "linux.pslist", "desc": "Lists active Linux processes."},
    {"id": "l_pstree", "label": " |- Process Tree", "plugin": "linux.pstree", "desc": "Process tree showing parent-child relationships."},
    {"id": "l_netstat", "label": " |- Network Connections", "plugin": "linux.check_afinfo", "desc": "Extracts active network connection sockets."},
    {"id": "l_mount", "label": " |- Mounted Filesystems", "plugin": "linux.mount", "desc": "Shows active mounted filesystems and devices."},
    {"id": "l_lsmod", "label": " |- Kernel Modules", "plugin": "linux.lsmod", "desc": "Lists currently loaded kernel drivers/modules."},
    {"id": "l_bash", "label": " |- Bash History", "plugin": "linux.bash", "desc": "Recovers bash command history from memory."},

    {"header": True, "label": ""}, 
    {"header": True, "label": "=== MAC ==="},
    {"id": "m_pslist", "label": " |- Processes (pslist)", "plugin": "mac.pslist", "desc": "Lists active Mac processes."},
    {"id": "m_pstree", "label": " |- Process Tree", "plugin": "mac.pstree", "desc": "Shows parent-child relationships."},
    {"id": "m_netstat", "label": " |- Network Connections", "plugin": "mac.netstat", "desc": "Extracts active network connections."},
    {"id": "m_mount", "label": " |- Mounted Filesystems", "plugin": "mac.mount", "desc": "Shows active mounted filesystems."},
    {"id": "m_lsmod", "label": " |- Kernel Modules", "plugin": "mac.lsmod", "desc": "Lists loaded kernel modules / extensions."},
]

class NonWrappingOptionList(OptionList):
    """A custom OptionList that completely overrides movement to prevent wrapping over headers."""
    
    def action_cursor_down(self) -> None:
        """Scan downwards for the next ENABLED item. If none found, do absolutely nothing."""
        if self.highlighted is None:
            self.highlighted = 0
            return
            
        for i in range(self.highlighted + 1, self.option_count):
            if not self.get_option_at_index(i).disabled:
                self.highlighted = i
                self.scroll_to_highlight()
                return

    def action_cursor_up(self) -> None:
        """Scan upwards for the next ENABLED item. If none found, do absolutely nothing."""
        if self.highlighted is None:
            self.highlighted = 0
            return
            
        for i in range(self.highlighted - 1, -1, -1):
            if not self.get_option_at_index(i).disabled:
                self.highlighted = i
                self.scroll_to_highlight()
                return


class QVI(App):
    """QVI - Quick Volatility Inspector Console Interface."""
    
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    $primary: #aa0000;
    $secondary: #660000;
    $accent: #ff0000;
    $text: #cccccc;
    $surface: #0a0a0a;
    $panel: #111111;
    $success: #aa0000;

    Screen {
        layout: horizontal;
        background: #000000;
    }

    *:focus {
        border: none;
        outline: none;
    }

    Header {
        background: #550000;
        color: #ffffff;
    }
    
    HeaderIcon { display: none; }

    Footer {
        background: #220000;
        color: #ffaaaa;
    }
    
    Footer > .footer--key {
        background: #880000;
        color: #ffffff;
        text-style: bold;
    }

    #left_pane {
        width: 35%;
        height: 100%;
        border: none;
        border-right: ascii #aa0000;
        background: #080808;
        /* Correct Textual Scrollbar Styling */
        scrollbar-color: #aa0000;
        scrollbar-color-hover: #ff3333;
        scrollbar-color-active: #ff0000;
        scrollbar-background: #080808;
    }
    
    #left_pane:focus {
        border: none;
        border-right: ascii #ff3333;
    }

    #right_pane {
        width: 65%;
        height: 100%;
        padding: 1 2;
        border: none;
        background: #000000;
        color: #bbbbbb;
        /* Correct Textual Scrollbar Styling */
        scrollbar-color: #aa0000;
        scrollbar-color-hover: #ff3333;
        scrollbar-color-active: #ff0000;
        scrollbar-background: #000000;
    }

    NonWrappingOptionList > .option-list--option-highlighted {
        background: #aa0000;
        color: #ffffff;
        text-style: bold;
    }

    NonWrappingOptionList > .option-list--option-disabled {
        color: #ff4444;
        text-style: bold;
        background: #1a0000;
    }

    MarkdownH1 {
        color: #ff3333;
        border-bottom: ascii #ff3333;
    }
    
    MarkdownH2, MarkdownH3 { color: #cc0000; }
    """

    BINDINGS =[
        ("q", "quit", "Quit"),
        ("escape,backspace,left", "go_back", "Go Back"),
        ("enter,right", "select_item", "Open Module"),
        ("j,down", "scroll_down", "Scroll Down"),
        ("k,up", "scroll_up", "Scroll Up")
    ]

    def __init__(self, dump_file: str):
        super().__init__()
        self.dump_file = dump_file
        self.current_level = "root"  
        self.cached_data = {}        
        self.active_category = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False) 
        with Horizontal():
            yield NonWrappingOptionList(id="left_pane")
            yield Markdown(id="right_pane") 
        yield Footer()

    def on_mount(self) -> None:
        self.title = f"QVI Inspector | {os.path.basename(self.dump_file)}"
        self.load_root_menu()

    def load_root_menu(self):
        self.current_level = "root"
        self.active_category = None
        left_pane = self.query_one("#left_pane", NonWrappingOptionList)
        left_pane.clear_options()
        
        for cat in CATEGORIES:
            if cat.get("header"):
                left_pane.add_option(Option(cat["label"], disabled=True))
            else:
                left_pane.add_option(Option(cat["label"], id=cat["id"]))
            
        left_pane.highlighted = 1
        self.update_right_pane()

    def load_items_menu(self, category_id: str):
        self.current_level = category_id
        self.active_category = next(c for c in CATEGORIES if c.get("id") == category_id)
        
        left_pane = self.query_one("#left_pane", NonWrappingOptionList)
        left_pane.clear_options()
        right_pane = self.query_one("#right_pane", Markdown)
        
        if category_id in self.cached_data:
            data = self.cached_data[category_id]
            
            # --- DYNAMIC PROCESS TREE (PSTREE) ANCESTRY CALCULATOR ---
            if "pstree" in self.active_category["plugin"]:
                pid_to_ppid = {}
                for item in data:
                    pid = item.get("PID") or item.get("Pid")
                    ppid = item.get("PPID") or item.get("Ppid")
                    if pid is not None:
                        pid_to_ppid[pid] = ppid
                        
                def get_depth(pid, seen=None):
                    if seen is None: seen = set()
                    if pid in seen: return 0  
                    seen.add(pid)
                    ppid = pid_to_ppid.get(pid)
                    if ppid is None or ppid == pid or ppid == 0 or ppid not in pid_to_ppid:
                        return 0
                    return 1 + get_depth(ppid, seen)
                    
                for item in data:
                    pid = item.get("PID") or item.get("Pid")
                    if pid is not None:
                        item["TreeDepth"] = get_depth(pid)
            # ---------------------------------------------------------

            for index, item in enumerate(data):
                pid = item.get("PID") or item.get("Pid")
                ppid = item.get("PPID") or item.get("Ppid")
                name = item.get("ImageFileName") or item.get("COMM") or item.get("Name") or item.get("Module") or item.get("Process")
                
                depth = item.get("TreeDepth", 0)
                indent = ""
                if depth > 0:
                    indent = " |" + "-" * depth + " "

                if item.get("User") and item.get("NTLM"): 
                    label = f"{item.get('User')} (NTLM: {item.get('NTLM')[:8]}...)"
                elif item.get("Args") and name: 
                    label = f"{indent}{name} -> {item.get('Args')[:30]}"
                elif item.get("Path") or item.get("FileName"): 
                    p = item.get("Path") or item.get("FileName")
                    label = f"File: {p[:40]}"
                elif item.get("Command"): 
                    label = f"Bash: {item.get('Command')[:40]}"
                elif pid is not None and name:
                    if ppid is not None and "pstree" in self.active_category["plugin"]:
                        label = f"{indent}[{pid}] {name} (PPID: {ppid})"
                    else:
                        label = f"{indent}[{pid}] {name}"
                elif item.get("Proto") and item.get("LocalAddr"):
                    label = f"{item.get('Proto')} {item.get('LocalAddr')}:{item.get('LocalPort', '')}"
                elif item.get("Variable") and item.get("Value"):
                    label = f"{item.get('Variable')}"
                elif item.get("Mount") or item.get("Device"):
                    label = f"{item.get('Device', 'Dev')} -> {item.get('Mount', 'Path')}"
                else:
                    vals =[str(v) for v in item.values() if isinstance(v, (str, int))]
                    label = vals[0][:40] if vals else f"Item {index}"
                    
                left_pane.add_option(Option(label, id=str(index)))
            
            if data:
                left_pane.highlighted = 0
                self.update_right_pane()
            else:
                right_pane.update("# No Data Found\n\nVolatility returned empty results. \n\n*If this dump is a different OS, press the Left Arrow and try a different category.*")
        else:
            right_pane.update(f"# Analyzing Memory...\n\nRunning **{self.active_category['plugin']}**.\n\n*This may take a few minutes. Please wait...*")
            self.run_volatility_plugin(self.active_category)

    @work(thread=True)
    def run_volatility_plugin(self, category):
        plugin = category["plugin"]
        cat_id = category["id"]
        
        env = os.environ.copy()
        env["VOL_DUMP_FILE"] = self.dump_file
        env["VOL_PLUGIN"] = plugin

        script = (
            "import sys, os\n"
            "from volatility3 import cli\n"
            "sys.argv =['vol', '-q', '-f', os.environ['VOL_DUMP_FILE'], '-r', 'json', os.environ['VOL_PLUGIN']]\n"
            "sys.exit(cli.main())\n"
        )
        
        cmd = [sys.executable, "-c", script]
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', env=env)
            stdout, stderr = process.communicate()
            
            json_start = stdout.find('[')
            json_end = stdout.rfind(']')
            
            if json_start != -1 and json_end != -1:
                json_str = stdout[json_start:json_end+1]
                try:
                    parsed_data = json.loads(json_str)
                    self.cached_data[cat_id] = parsed_data
                    self.call_from_thread(self.load_items_menu, cat_id)
                except json.JSONDecodeError:
                    self.call_from_thread(self.show_error, f"Failed to parse JSON. Raw Output:\n\n{stdout}")
            else:
                error_msg = stderr.strip() or stdout.strip() or "No data returned. This might be the wrong OS module."
                self.call_from_thread(self.show_error, error_msg)
                
        except Exception as e:
            self.call_from_thread(self.show_error, str(e))

    def show_error(self, error_msg):
        right_pane = self.query_one("#right_pane", Markdown)
        right_pane.update(f"# Volatility Error\n\n```text\n{error_msg}\n```\n\n*Press the Left Arrow to go back.*")

    def update_right_pane(self):
        left_pane = self.query_one("#left_pane", NonWrappingOptionList)
        right_pane = self.query_one("#right_pane", Markdown)
        
        if left_pane.highlighted is None:
            return

        if self.current_level == "root":
            cat_id = left_pane.get_option_at_index(left_pane.highlighted).id
            if cat_id:
                cat = next(c for c in CATEGORIES if c.get("id") == cat_id)
                right_pane.update(f"# {cat['label'].strip(' |-')}\n\n{cat['desc']}\n\n---\n> **Press 'Enter' or 'Right Arrow' to analyze.**")
            
        else:
            if self.current_level in self.cached_data:
                data = self.cached_data[self.current_level]
                if len(data) > left_pane.highlighted:
                    item = data[left_pane.highlighted]
                    
                    label_clean = self.active_category['label'].replace(" |- ", "")
                    details = f"# {label_clean} Details\n\n---\n\n"
                    for key, value in item.items():
                        if key in ["TreeDepth", "Offset"]: continue 
                        details += f"**{key}:** `{value}`\n\n"
                        
                    right_pane.update(details)

    @on(OptionList.OptionSelected)
    def handle_enter(self, event: OptionList.OptionSelected) -> None:
        self.action_select_item()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self.update_right_pane()

    def action_select_item(self) -> None:
        if self.current_level == "root":
            left_pane = self.query_one("#left_pane", NonWrappingOptionList)
            if left_pane.highlighted is not None:
                cat_id = left_pane.get_option_at_index(left_pane.highlighted).id
                if cat_id: 
                    self.load_items_menu(cat_id)

    def action_go_back(self) -> None:
        if self.current_level != "root":
            self.load_root_menu()

    def action_scroll_down(self) -> None:
        if self.current_level != "root":
            self.query_one("#right_pane", Markdown).scroll_down()

    def action_scroll_up(self) -> None:
        if self.current_level != "root":
            self.query_one("#right_pane", Markdown).scroll_up()

# ============================================================================
# 3. ENTRY POINT & CRASH HANDLER
# ============================================================================
def main():
    if len(sys.argv) < 2:
        print("\n[!] ERROR: You must provide a memory dump file!")
        print("Usage: python QVI.py <path_to_memory_dump.raw>\n")
        print("[*] TIP: You can simply DRAG AND DROP your .raw memory dump file")
        print("         directly onto this QVI.py script in Windows!\n")
        input("Press Enter to close this window...")
        sys.exit(1)
        
    dump_path = sys.argv[1]
    
    if not os.path.exists(dump_path):
        print(f"\n[!] ERROR: Memory dump file not found at: '{dump_path}'")
        input("\nPress Enter to close this window...")
        sys.exit(1)

    app = QVI(dump_path)
    app.run()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        with open("QVI_crash.log", "w") as f:
            f.write(traceback.format_exc())
            
        print("\n" + "="*60)
        print("[CRASH] Application Encountered a Fatal Error")
        print("="*60)
        print(f"Details: {e}")
        print("\nA full crash log has been saved to 'QVI_crash.log' in this folder.")
        print("="*60)
        input("\nPress Enter to exit...")