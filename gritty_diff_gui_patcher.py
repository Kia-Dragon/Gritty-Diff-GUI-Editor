#!/usr/bin/env python3
"""
Gritty Diff GUI Patcher — Single-file Tkinter application
Compatible with Python 3.12 (and 3.7+)

What it does:
- Choose your project root and paste a unified diff
- Click "Process Diff" to parse files/hunks
- Select a file from the list, then:
  - Display Change: colorized view of +/-/context
  - AUTO EDIT: backup → apply patch → write
  - VERIFY: check edited file matches patch result
  - UNDO: restore most recent backup
- Next Pending: jumps to the next unverified file
- Shows green "ALL DONE" when all files verified

No external dependencies - uses standard library only.
"""

import io
import os
import sys
import time
import shutil
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

# ---------------------------- Configuration Management ----------------------------

class Config:
    """Manage application configuration and persistence"""
    
    def __init__(self):
        # Try multiple locations for config file
        try:
            # Try user home directory first
            home = os.path.expanduser("~")
            if home == "~":  # expanduser failed
                home = os.environ.get('USERPROFILE', os.getcwd())  # Windows fallback
            self.config_file = os.path.join(home, ".diff_gui_patcher_config.json")
        except:
            # If all else fails, use current directory
            self.config_file = os.path.join(os.getcwd(), ".diff_gui_patcher_config.json")
        
        # Initialize with empty data
        self.data = {"default_root": os.getcwd(), "version": "1.0"}
        
        # Try to load existing config
        try:
            self.load()
        except:
            pass  # Use defaults if loading fails
    
    def load(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict):
                        self.data.update(loaded_data)
            except:
                pass  # Keep defaults on any error
    
    def save(self):
        """Save configuration to file - best effort, ignore failures"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass  # Silently fail if can't save
    
    def get_default_root(self) -> str:
        """Get the default project root directory"""
        default = self.data.get("default_root", os.getcwd())
        # Return the default if it exists, otherwise current directory
        return default if os.path.isdir(default) else os.getcwd()
    
    def set_default_root(self, path: str):
        """Set the default project root directory"""
        if os.path.isdir(path):
            self.data["default_root"] = path
            self.save()

# ---------------------------- Data Models ----------------------------

@dataclass
class Hunk:
    """Represents a single hunk in a unified diff"""
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: List[str]  # includes leading ' ', '+', '-'

@dataclass
class PatchFile:
    """Represents a file to be patched with its hunks and status"""
    old_path: str
    new_path: str
    hunks: List[Hunk] = field(default_factory=list)
    status: str = "pending"  # pending | edited | verified_ok | verify_failed
    last_backup: Optional[str] = None

# ---------------------------- Diff Parsing & Applying ----------------------------

def _strip_prefix(path: str) -> str:
    """Remove common diff prefixes like a/ b/"""
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path

def parse_unified_diff(text: str) -> List[PatchFile]:
    """
    Parse unified diff format (git-style diffs).
    Returns list of PatchFile objects with their hunks.
    """
    lines = text.splitlines()
    i = 0
    files: List[PatchFile] = []

    while i < len(lines):
        line = lines[i]
        
        # Look for file header
        if line.startswith("--- "):
            old_path = line[4:].strip()
            old_path = _strip_prefix(old_path)
            
            i += 1
            if i >= len(lines) or not lines[i].startswith("+++ "):
                # Malformed diff, skip this entry
                continue
                
            new_path = lines[i][4:].strip()
            new_path = _strip_prefix(new_path)
            
            pf = PatchFile(old_path=old_path, new_path=new_path, hunks=[])
            i += 1

            # Read hunks for this file
            while i < len(lines) and lines[i].startswith("@@"):
                header = lines[i]
                
                # Parse hunk header: @@ -l,s +l,s @@ optional context
                try:
                    # Extract content between @@ markers
                    at1 = header.find("@@")
                    at2 = header.find("@@", at1 + 2)
                    if at2 == -1:
                        i += 1
                        continue
                        
                    core = header[at1+2:at2].strip()
                    parts = core.split()
                    
                    if len(parts) < 2:
                        i += 1
                        continue
                        
                    old_part = parts[0]  # like -12,5
                    new_part = parts[1]  # like +12,7
                    
                    def parse_range(part_str):
                        """Parse -l,s or +l,s format"""
                        part_str = part_str.strip()
                        if not part_str or part_str[0] not in "+-":
                            return None, None
                        part_str = part_str[1:]
                        
                        if "," in part_str:
                            start_str, len_str = part_str.split(",", 1)
                            return int(start_str), int(len_str)
                        else:
                            return int(part_str), 1
                    
                    old_start, old_len = parse_range(old_part)
                    new_start, new_len = parse_range(new_part)
                    
                    if old_start is None or new_start is None:
                        i += 1
                        continue
                        
                except (ValueError, IndexError):
                    # Malformed hunk header, skip
                    i += 1
                    continue

                i += 1
                hunk_lines: List[str] = []
                
                # Collect hunk content lines
                while i < len(lines):
                    if lines[i] and lines[i][0] in " +-":
                        hunk_lines.append(lines[i])
                        i += 1
                    elif lines[i].startswith("\\"):
                        # "\ No newline at end of file" - skip
                        i += 1
                    else:
                        break
                        
                if hunk_lines:
                    pf.hunks.append(Hunk(old_start, old_len, new_start, new_len, hunk_lines))
                    
            if pf.hunks:
                files.append(pf)
        else:
            i += 1

    # Merge duplicate entries for same file
    merged: Dict[str, PatchFile] = {}
    for pf in files:
        key = pf.new_path or pf.old_path
        if key in merged:
            merged[key].hunks.extend(pf.hunks)
        else:
            merged[key] = pf
            
    # Sort hunks by position for each file
    result = []
    for key, pf in merged.items():
        pf.hunks.sort(key=lambda h: (h.old_start, h.new_start))
        result.append(pf)
        
    return result

def detect_line_ending(text: str) -> str:
    """Detect the line ending style used in text"""
    if '\r\n' in text:
        return '\r\n'
    elif '\r' in text:
        return '\r'
    else:
        return '\n'

def apply_hunks_to_text(original: str, hunks: List[Hunk]) -> str:
    """
    Apply hunks to original content and return patched text.
    Assumes hunks are valid and ordered by old_start.
    Properly handles line endings and context verification.
    """
    # Handle empty original file
    if not original:
        orig_lines = []
        line_ending = '\n'
    else:
        # Preserve original line ending style
        line_ending = detect_line_ending(original)
        # Split into lines without endings for easier processing
        orig_lines = original.splitlines()
    
    output: List[str] = []
    idx = 0  # Current index in orig_lines (0-based)
    
    for hunk_num, hunk in enumerate(hunks):
        # Copy unchanged lines up to hunk start (convert 1-based to 0-based)
        target_idx = max(0, hunk.old_start - 1)
        
        # Add unchanged lines before this hunk
        while idx < target_idx and idx < len(orig_lines):
            output.append(orig_lines[idx])
            idx += 1
        
        # Track lines consumed from original for this hunk
        hunk_old_consumed = 0
        
        # Process hunk lines
        for hunk_line in hunk.lines:
            if not hunk_line:
                continue
                
            tag = hunk_line[0]
            content = hunk_line[1:]
            
            # Remove any line endings from content
            content = content.rstrip('\r\n')
                
            if tag == ' ':
                # Context line: should match original
                if idx < len(orig_lines):
                    # Use original line to preserve exact formatting
                    output.append(orig_lines[idx])
                    idx += 1
                    hunk_old_consumed += 1
                else:
                    # Original file is shorter than expected
                    # This might indicate a problem, but add the context line anyway
                    output.append(content)
                    hunk_old_consumed += 1
                    
            elif tag == '-':
                # Deletion: skip original line
                if idx < len(orig_lines):
                    idx += 1
                    hunk_old_consumed += 1
                # If we're beyond the end of original, that's an error but continue
                    
            elif tag == '+':
                # Addition: insert new content
                output.append(content)
                # Additions don't consume from old file
                
    # Append any remaining original lines
    while idx < len(orig_lines):
        output.append(orig_lines[idx])
        idx += 1
    
    # Join with detected line ending
    if output:
        result = line_ending.join(output)
    else:
        result = ""
    
    # Handle final newline if original had one
    if original and original[-1] in '\r\n':
        if not result or result[-1] not in '\r\n':
            result += line_ending
    
    return result

# ---------------------------- GUI Application ----------------------------

class DiffGuiApp(tk.Tk):
    """Main application window for the Gritty Diff GUI Patcher"""
    
    def __init__(self):
        super().__init__()
        self.title("Gritty Diff GUI Patcher - Python 3.12")
        self.geometry("1200x800")
        
        # Initialize config with error handling (renamed to avoid collision with tk.config)
        try:
            self.app_config = Config()
            default_root = self.app_config.get_default_root()
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
            self.app_config = None
            default_root = os.getcwd()
        
        # Initialize state
        self.project_root = tk.StringVar(value=default_root)
        self.patch_files: List[PatchFile] = []
        self.file_index_map: Dict[str, int] = {}
        self.selected_file_key: Optional[str] = None
        
        # Build UI
        self._build_ui()
        self._populate_tree()
        
        # Bind tree expansion event
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_expand)
        
    def _build_ui(self):
        """Create the user interface"""
        
        # Create menu bar
        self._create_menu()
        
        # Top frame: project root selector and completion indicator
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=8)
        
        ttk.Label(top_frame, text="Project root:").pack(side="left")
        self.root_entry = ttk.Entry(top_frame, textvariable=self.project_root, width=60)
        self.root_entry.pack(side="left", padx=6)
        ttk.Button(top_frame, text="Browse...", command=self._choose_root).pack(side="left")
        
        self.done_indicator = ttk.Label(top_frame, text="")
        self.done_indicator.pack(side="right", padx=10)
        
        # Main paned window
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=8)
        
        # Left pane: directory tree
        left_frame = ttk.Frame(paned)
        
        self.tree = ttk.Treeview(left_frame, columns=("fullpath",), displaycolumns=())
        tree_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="left", fill="y")
        
        paned.add(left_frame, weight=1)
        
        # Right pane: main controls
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        
        # Diff input area
        diff_frame = ttk.LabelFrame(right_frame, text="Unified Diff Input")
        diff_frame.pack(fill="both", expand=False, padx=4, pady=(0, 6))
        
        # LLM Output Contract definition
        contract_frame = ttk.Frame(diff_frame)
        contract_frame.pack(fill="x", padx=6, pady=(6, 0))
        
        ttk.Label(contract_frame, text="Use this in your LLM prompt to get the properly formatted diff file for code edits:", 
                 font=("TkDefaultFont", 9, "bold")).pack(side="left")
        
        ttk.Button(contract_frame, text="PRE PROMPT", 
                  command=self._show_output_contract).pack(side="right")
        
        self.diff_text = tk.Text(diff_frame, height=12, wrap="none", bg="white")
        self.diff_text.pack(fill="both", expand=True, padx=6, pady=6)
        
        # Buttons for diff processing
        button_frame = ttk.Frame(diff_frame)
        button_frame.pack(anchor="e", padx=6, pady=(0, 6))
        
        ttk.Button(button_frame, text="Reset", command=self._reset).pack(side="right", padx=3)
        ttk.Button(button_frame, text="Process Diff", command=self._process_diff).pack(side="right")
        
        # File list and action buttons
        middle_frame = ttk.Frame(right_frame)
        middle_frame.pack(fill="both", expand=True)
        
        self.files_list = tk.Listbox(middle_frame, height=12, activestyle="dotbox", bg="white")
        self.files_list.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.files_list.bind("<<ListboxSelect>>", self._on_file_select)
        
        # Action buttons
        buttons_frame = ttk.Frame(middle_frame)
        buttons_frame.pack(side="left", fill="y")
        
        ttk.Button(buttons_frame, text="Display Change", command=self._display_change).pack(fill="x", pady=3)
        ttk.Button(buttons_frame, text="AUTO EDIT", command=self._auto_edit).pack(fill="x", pady=3)
        ttk.Button(buttons_frame, text="VERIFY", command=self._verify).pack(fill="x", pady=3)
        
        self.undo_btn = ttk.Button(buttons_frame, text="UNDO (last backup)", 
                                   command=self._undo, state="disabled")
        self.undo_btn.pack(fill="x", pady=3)
        
        ttk.Separator(buttons_frame, orient="horizontal").pack(fill="x", pady=8)
        
        self.next_btn = ttk.Button(buttons_frame, text="Next Pending ▶", 
                                   command=self._select_next_pending, state="disabled")
        self.next_btn.pack(fill="x", pady=3)
        
        ttk.Button(buttons_frame, text="Exit", command=self.destroy).pack(fill="x", pady=(20, 3))
        
        # Log area
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill="both", expand=True, padx=4, pady=(6, 0))
        
        self.log = tk.Text(log_frame, height=10, wrap="word", bg="white")
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        
        # Configure log colors
        self.log.tag_configure("ok", foreground="green")
        self.log.tag_configure("err", foreground="red")
        self.log.tag_configure("info", foreground="blue")
        
        self._log("Ready. Choose project root, paste unified diff, click Process Diff.")
    
    def _show_output_contract(self):
        """Display the LLM Output Contract splash screen"""
        # Create modal dialog
        dialog = tk.Toplevel(self)
        dialog.title("OUTPUT CONTRACT — UNIFIED DIFF ONLY")
        dialog.geometry("800x600")
        dialog.resizable(True, True)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (dialog.winfo_screenheight() // 2) - (600 // 2)
        dialog.geometry(f"800x600+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ttk.Label(main_frame, text="OUTPUT CONTRACT — UNIFIED DIFF ONLY", 
                               font=("TkDefaultFont", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Contract text
        contract_text = """You must output a single fenced code block labeled patch that contains a valid unified diff and nothing else. No prose before or after. Do not add syntax highlighting, colors, or explanations.

REQUIRED FORMAT:
- File headers: 
  --- a/<path/to/file>
  +++ b/<path/to/file>
- Hunk headers:
  @@ -<oldStart>,<oldLen> +<newStart>,<newLen> @@
- Hunk body lines MUST start with exactly one of:
  " " (space) for context, "-" for deletions, "+" for additions.
  A visually blank context line MUST be " " followed by newline (NOT an empty line).
- If a file previously had no final newline, include the literal line:
  \\ No newline at end of file
- Use LF newlines (\\n). Do not include tabs for leading markers.
- End the diff with a newline.

CONSTRAINTS:
- Emit exactly one code block:
  ```patch
  <unified diff here>
  ```"""
        
        # Text widget for contract
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        text_widget = tk.Text(text_frame, wrap="word", bg="white", 
                             font=("Courier", 10), state="normal")
        text_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scrollbar.set)
        
        text_widget.pack(side="left", fill="both", expand=True)
        text_scrollbar.pack(side="right", fill="y")
        
        text_widget.insert("1.0", contract_text)
        text_widget.configure(state="disabled")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # Copy status indicator
        self.copy_indicator = ttk.Label(button_frame, text="", foreground="green")
        self.copy_indicator.pack(side="left")
        
        def copy_contract():
            """Copy the contract text to clipboard"""
            try:
                dialog.clipboard_clear()
                dialog.clipboard_append(contract_text)
                self.copy_indicator.configure(text="✓ Copied to clipboard!")
                # Clear the indicator after 3 seconds
                dialog.after(3000, lambda: self.copy_indicator.configure(text=""))
            except Exception as e:
                self.copy_indicator.configure(text=f"Copy failed: {e}", foreground="red")
        
        def close_dialog():
            dialog.destroy()
        
        # Buttons
        ttk.Button(button_frame, text="Close", command=close_dialog).pack(side="right", padx=(10, 0))
        ttk.Button(button_frame, text="COPY", command=copy_contract).pack(side="right")
        
        # Bind Escape key to close
        dialog.bind("<Escape>", lambda e: close_dialog())
        
        # Wait for dialog
        self.wait_window(dialog)
        
    def _create_menu(self):
        """Create the menu bar"""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Set Project Root...", command=self._choose_root)
        file_menu.add_command(label="Reset Default Root", command=self._reset_default_root)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear Diff", command=lambda: self.diff_text.delete("1.0", "end"))
        edit_menu.add_command(label="Reset All", command=self._reset)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh Tree", command=self._populate_tree)
        view_menu.add_command(label="Clear Log", command=lambda: self.log.delete("1.0", "end"))
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Show Config Location", command=self._show_config_location)
    
    def _reset_default_root(self):
        """Reset the default root directory to current working directory"""
        cwd = os.getcwd()
        if self.app_config:
            try:
                self.app_config.set_default_root(cwd)
                self.project_root.set(cwd)
                self._populate_tree()
                self._log(f"Default root reset to: {cwd}", "info")
                messagebox.showinfo("Default Reset", f"Default project root has been reset to:\n{cwd}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not reset default: {e}")
        else:
            self.project_root.set(cwd)
            self._populate_tree()
            messagebox.showinfo("Note", "Config unavailable. Set to current directory temporarily.")
    
    def _show_about(self):
        """Show about dialog"""
        about_text = """Gritty Diff GUI Patcher
Version 1.2 (Enhanced)
Python 3.12 Compatible

A single-file tool for applying unified diffs
with visual feedback and safety features.

New Features:
• LLM Output Contract for standardized diff generation
• PRE PROMPT button for easy contract copying

Core Features:
• Automatic backups
• Visual diff display
• Patch verification
• Undo functionality
• Persistent default directory

No external dependencies required."""
        messagebox.showinfo("About Gritty Diff GUI Patcher", about_text)
    
    def _show_config_location(self):
        """Show where the config file is stored"""
        if self.app_config:
            config_path = self.app_config.config_file
            exists = "exists" if os.path.exists(config_path) else "does not exist"
            message = f"Configuration file location:\n{config_path}\n\nFile {exists}."
        else:
            config_path = os.path.join(os.path.expanduser("~"), ".diff_gui_patcher_config.json")
            message = f"Configuration system unavailable.\nExpected location:\n{config_path}"
        messagebox.showinfo("Config Location", message)
    
    def _choose_root(self):
        """Select project root directory with option to set as default"""
        
        # Create custom dialog
        dialog = tk.Toplevel(self)
        dialog.title("Select Project Root")
        dialog.geometry("500x150")
        dialog.resizable(False, False)
        
        # Center the dialog
        dialog.transient(self)
        dialog.grab_set()
        
        # Variables for dialog
        selected_path = tk.StringVar(value=self.project_root.get())
        set_as_default = tk.BooleanVar(value=False)
        
        # Path selection frame
        path_frame = ttk.Frame(dialog)
        path_frame.pack(fill="x", padx=20, pady=20)
        
        ttk.Label(path_frame, text="Directory:").pack(side="left")
        path_entry = ttk.Entry(path_frame, textvariable=selected_path, width=50)
        path_entry.pack(side="left", padx=10)
        
        def browse_folder():
            directory = filedialog.askdirectory(
                initialdir=selected_path.get(),
                title="Select Project Root Directory"
            )
            if directory:
                selected_path.set(directory)
        
        ttk.Button(path_frame, text="Browse...", command=browse_folder).pack(side="left")
        
        # Checkbox for setting as default
        checkbox_frame = ttk.Frame(dialog)
        checkbox_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ttk.Checkbutton(
            checkbox_frame,
            text="Set as default project root",
            variable=set_as_default
        ).pack(side="left")
        
        # Buttons frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        def ok_clicked():
            path = selected_path.get()
            if path and os.path.isdir(path):
                self.project_root.set(path)
                self._populate_tree()
                
                # Save as default if requested
                if set_as_default.get():
                    if self.app_config:
                        try:
                            self.app_config.set_default_root(path)
                            self._log(f"Default project root updated: {path}", "info")
                        except Exception as e:
                            self._log(f"Could not save default: {e}", "err")
                    else:
                        self._log("Config system unavailable, cannot save default", "err")
                else:
                    self._log(f"Project root set to: {path}", "info")
                
                dialog.destroy()
            else:
                messagebox.showerror("Invalid Directory", "Please select a valid directory.")
        
        def cancel_clicked():
            dialog.destroy()
        
        ttk.Button(button_frame, text="OK", command=ok_clicked, width=10).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel_clicked, width=10).pack(side="right")
        
        # Focus on the path entry
        path_entry.focus_set()
        
        # Wait for dialog to close
        self.wait_window(dialog)
            
    def _populate_tree(self):
        """Populate directory tree view"""
        self.tree.delete(*self.tree.get_children())
        root_path = self.project_root.get()
        
        if not os.path.isdir(root_path):
            return
            
        root_name = os.path.basename(root_path) or root_path
        root_node = self.tree.insert("", "end", text=root_name, open=True, values=(root_path,))
        self._add_tree_items(root_node, root_path)
        
    def _add_tree_items(self, parent_node, directory):
        """Recursively add items to tree"""
        try:
            entries = sorted(os.listdir(directory))
        except (PermissionError, OSError):
            return
            
        for name in entries:
            # Skip hidden files and common non-source directories
            if name.startswith('.') or name in ('__pycache__', 'node_modules'):
                continue
                
            full_path = os.path.join(directory, name)
            node = self.tree.insert(parent_node, "end", text=name, 
                                   open=False, values=(full_path,))
            
            if os.path.isdir(full_path):
                # Add a dummy child to show expand arrow
                self.tree.insert(node, "end", text="")
                # Bind expand event to lazy load
                self.tree.item(node, tags=("unexpanded",))
                
    def _on_tree_expand(self, event):
        """Lazy load tree items on expand"""
        item = self.tree.focus()
        if "unexpanded" in self.tree.item(item, "tags"):
            # Remove dummy child and load real items
            children = self.tree.get_children(item)
            for child in children:
                self.tree.delete(child)
            
            path = self.tree.set(item, "fullpath")
            self._add_tree_items(item, path)
            
            # Remove unexpanded tag
            tags = list(self.tree.item(item, "tags"))
            tags.remove("unexpanded")
            self.tree.item(item, tags=tags)
            
    def _highlight_in_tree(self, full_path: str):
        """Highlight and reveal item in tree"""
        def find_and_select(node):
            if self.tree.set(node, "fullpath") == full_path:
                self.tree.see(node)
                self.tree.selection_set(node)
                return True
            for child in self.tree.get_children(node):
                if find_and_select(child):
                    self.tree.item(node, open=True)
                    return True
            return False
            
        for root_item in self.tree.get_children(""):
            if find_and_select(root_item):
                break
                
    def _log(self, message: str, tag: Optional[str] = None):
        """Add timestamped message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {message}\n", (tag,) if tag else ())
        self.log.see("end")
        
    def _reset(self):
        """Clear all data and reset to initial state"""
        self.patch_files = []
        self.file_index_map = {}
        self.selected_file_key = None
        self.files_list.delete(0, "end")
        self.diff_text.delete("1.0", "end")
        self.next_btn.configure(state="disabled")
        self.undo_btn.configure(state="disabled")
        self._update_done_indicator()
        self._log("Reset complete. Ready for new diff.", "info")
        
    def _process_diff(self):
        """Parse and process the unified diff"""
        diff_content = self.diff_text.get("1.0", "end").strip()
        
        if not diff_content:
            messagebox.showinfo("No Diff", "Please paste a unified diff first.")
            return
            
        try:
            parsed_files = parse_unified_diff(diff_content)
        except Exception as e:
            messagebox.showerror("Parse Error", f"Failed to parse diff:\n{str(e)}")
            return
            
        if not parsed_files:
            messagebox.showwarning("Empty Diff", "No patchable files found in the diff.")
            return
            
        self.patch_files = parsed_files
        self.file_index_map = {pf.new_path: idx for idx, pf in enumerate(self.patch_files)}
        
        self._refresh_files_list()
        self._update_done_indicator()
        self._log(f"Parsed diff: {len(self.patch_files)} file(s) with "
                 f"{sum(len(pf.hunks) for pf in self.patch_files)} total hunks.", "ok")
        
        self.next_btn.configure(state="normal")
        
    def _refresh_files_list(self):
        """Update the files list display"""
        self.files_list.delete(0, "end")
        for pf in self.patch_files:
            self.files_list.insert("end", self._get_file_label(pf))
            
    def _get_file_label(self, pf: PatchFile) -> str:
        """Generate display label for a patch file"""
        status_marks = {
            "pending": "⏳",
            "edited": "✎",
            "verified_ok": "✅",
            "verify_failed": "❌",
        }
        mark = status_marks.get(pf.status, "•")
        return f"{mark} {pf.new_path} ({len(pf.hunks)} hunks)"
        
    def _on_file_select(self, event=None):
        """Handle file selection in list"""
        selection = self.files_list.curselection()
        if not selection:
            return
            
        idx = selection[0]
        pf = self.patch_files[idx]
        self.selected_file_key = pf.new_path
        
        # Highlight in tree
        full_path = os.path.join(self.project_root.get(), pf.new_path)
        self._highlight_in_tree(full_path)
        
        # Update undo button state
        self.undo_btn.configure(state="normal" if pf.last_backup else "disabled")
        
    def _get_selected_patch_file(self) -> Optional[PatchFile]:
        """Get currently selected patch file"""
        selection = self.files_list.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a file from the list first.")
            return None
        return self.patch_files[selection[0]]
        
    def _display_change(self):
        """Display diff for selected file in new window"""
        pf = self._get_selected_patch_file()
        if not pf:
            return
            
        # Create display window
        window = tk.Toplevel(self)
        window.title(f"Diff: {pf.new_path}")
        window.geometry("800x600")
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        text = tk.Text(text_frame, wrap="none", bg="white")
        scroll_y = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        scroll_x = ttk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        text.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        
        # Configure colors
        text.tag_configure("del", foreground="red")
        text.tag_configure("add", foreground="green")
        text.tag_configure("ctx", foreground="#666666")
        text.tag_configure("header", foreground="blue", font=("Courier", 10, "bold"))
        
        # Display hunks
        for hunk in pf.hunks:
            header = f"@@ -{hunk.old_start},{hunk.old_len} +{hunk.new_start},{hunk.new_len} @@\n"
            text.insert("end", header, ("header",))
            
            for line in hunk.lines:
                if not line:
                    continue
                    
                tag = line[0]
                content = line + ("\n" if not line.endswith("\n") else "")
                
                if tag == "-":
                    text.insert("end", content, ("del",))
                elif tag == "+":
                    text.insert("end", content, ("add",))
                else:
                    text.insert("end", content, ("ctx",))
                    
        text.configure(state="disabled")
        
        # Close button
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=10)
        
    def _make_backup(self, file_path: str) -> str:
        """Create timestamped backup of file"""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = f"{file_path}.bak.{timestamp}"
        shutil.copy2(file_path, backup_path)
        return backup_path
        
    def _auto_edit(self):
        """Apply patch to selected file"""
        pf = self._get_selected_patch_file()
        if not pf:
            return
            
        full_path = os.path.join(self.project_root.get(), pf.new_path)
        
        # Check file exists
        if not os.path.exists(full_path):
            messagebox.showerror("File Not Found", 
                               f"Target file does not exist:\n{full_path}")
            return
            
        try:
            # Read original content
            with open(full_path, "r", encoding="utf-8", errors="surrogateescape") as f:
                original_content = f.read()
        except Exception as e:
            messagebox.showerror("Read Error", 
                               f"Could not read file:\n{full_path}\n\n{str(e)}")
            return
            
        try:
            # Apply patches
            patched_content = apply_hunks_to_text(original_content, pf.hunks)
        except Exception as e:
            messagebox.showerror("Patch Error", 
                               f"Failed to apply patch:\n{pf.new_path}\n\n{str(e)}")
            return
            
        try:
            # Create backup
            backup_path = self._make_backup(full_path)
            
            # Detect original line ending style and write accordingly
            # Use binary mode to preserve exact line endings
            with open(full_path, "wb") as f:
                # Convert string to bytes with UTF-8 encoding
                f.write(patched_content.encode("utf-8", errors="surrogateescape"))
                
            # Update status
            pf.status = "edited"
            pf.last_backup = backup_path
            
            self._log(f"AUTO EDIT complete: {pf.new_path} "
                     f"(backup: {os.path.basename(backup_path)})", "ok")
            self._update_file_status(pf)
            
        except Exception as e:
            messagebox.showerror("Write Error", 
                               f"Failed to write patched file:\n{full_path}\n\n{str(e)}")
            return
            
    def _verify(self):
        """Verify that patch was applied correctly"""
        pf = self._get_selected_patch_file()
        if not pf:
            return
            
        full_path = os.path.join(self.project_root.get(), pf.new_path)
        
        if not os.path.exists(full_path):
            messagebox.showerror("File Not Found", 
                               f"Target file does not exist:\n{full_path}")
            return
            
        try:
            # Read current content
            with open(full_path, "r", encoding="utf-8", errors="surrogateescape") as f:
                current_content = f.read()
        except Exception as e:
            messagebox.showerror("Read Error", 
                               f"Could not read file:\n{full_path}\n\n{str(e)}")
            return
            
        try:
            # Get original content (from backup if available)
            if pf.last_backup and os.path.exists(pf.last_backup):
                with open(pf.last_backup, "r", encoding="utf-8", errors="surrogateescape") as f:
                    original_content = f.read()
            else:
                # No backup available, can't verify properly
                messagebox.showwarning("No Backup", 
                                     "Cannot verify without backup. Apply patch first.")
                return
                
            # Compute expected result
            expected_content = apply_hunks_to_text(original_content, pf.hunks)
            
        except Exception as e:
            messagebox.showerror("Verify Error", 
                               f"Failed to compute expected result:\n{str(e)}")
            return
            
        # Compare - normalize line endings for comparison
        def normalize_endings(text):
            return text.replace('\r\n', '\n').replace('\r', '\n')
        
        if normalize_endings(expected_content) == normalize_endings(current_content):
            pf.status = "verified_ok"
            self._log(f"VERIFY OK: {pf.new_path}", "ok")
        else:
            pf.status = "verify_failed"
            self._log(f"VERIFY FAILED: {pf.new_path}", "err")
            
            # Show diff details for debugging
            exp_lines = expected_content.splitlines()
            cur_lines = current_content.splitlines()
            self._log(f"  Expected {len(exp_lines)} lines, got {len(cur_lines)} lines", "err")
            
        self._update_file_status(pf)
        
        # Auto-jump to next pending file
        self.after(50, self._select_next_pending)
        
    def _undo(self):
        """Restore file from backup"""
        pf = self._get_selected_patch_file()
        if not pf:
            return
            
        if not pf.last_backup or not os.path.exists(pf.last_backup):
            messagebox.showinfo("No Backup", "No backup available for this file.")
            return
            
        target_path = os.path.join(self.project_root.get(), pf.new_path)
        
        try:
            shutil.copy2(pf.last_backup, target_path)
            pf.status = "pending"
            self._log(f"UNDO complete: restored from {os.path.basename(pf.last_backup)}", "info")
            self._update_file_status(pf)
        except Exception as e:
            messagebox.showerror("Undo Error", f"Failed to restore backup:\n{str(e)}")
            
    def _update_file_status(self, pf: PatchFile):
        """Update UI after file status change"""
        idx = self.file_index_map.get(pf.new_path)
        if idx is not None:
            # Update list item
            self.files_list.delete(idx)
            self.files_list.insert(idx, self._get_file_label(pf))
            
            # Restore selection
            self.files_list.selection_clear(0, "end")
            self.files_list.selection_set(idx)
            
        # Update undo button
        self.undo_btn.configure(state="normal" if pf.last_backup else "disabled")
        
        # Update completion indicator
        self._update_done_indicator()
        
    def _update_done_indicator(self):
        """Update the completion status indicator"""
        if not self.patch_files:
            self.done_indicator.configure(text="", foreground="black")
            return
            
        pending = [pf for pf in self.patch_files if pf.status != "verified_ok"]
        
        if not pending:
            self.done_indicator.configure(text="✅ ALL EDITS COMPLETE", foreground="green")
            self.next_btn.configure(state="disabled")
        else:
            remaining = len(pending)
            total = len(self.patch_files)
            self.done_indicator.configure(
                text=f"{remaining}/{total} files remaining", 
                foreground="orange"
            )
            
    def _select_next_pending(self):
        """Jump to next file that needs processing"""
        for i, pf in enumerate(self.patch_files):
            if pf.status != "verified_ok":
                self.files_list.selection_clear(0, "end")
                self.files_list.selection_set(i)
                self.files_list.see(i)
                self._on_file_select()
                self._log(f"Selected next pending: {pf.new_path}")
                return
                
        self._log("No pending files remain. All done!", "ok")
        self._update_done_indicator()

# ---------------------------- Main Entry Point ----------------------------

def main():
    """Main entry point for the application"""
    try:
        app = DiffGuiApp()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Application failed to start:\n{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
