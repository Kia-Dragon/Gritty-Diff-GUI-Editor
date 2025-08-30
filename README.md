# Gritty Diff GUI Patcher

A powerful, single-file Python GUI application for applying unified diff patches with visual feedback, automatic backups, and comprehensive safety features.

## Overview

Gritty Diff GUI Patcher transforms the traditionally complex process of applying patches into an intuitive, visual workflow. Whether you're applying code review suggestions, distributing patches across team members, or performing large-scale refactoring, this tool provides a safe and efficient way to handle unified diffs.

## Features

### Core Functionality
- **Visual File Browser** - Navigate your project structure with an integrated directory tree
- **Intelligent Diff Parsing** - Handles standard git diff format with multiple files and hunks
- **One-Click Patch Application** - Apply changes with automatic backup creation
- **Verification System** - Confirms patches were applied correctly by comparing expected vs actual results
- **Instant Rollback** - One-click undo using timestamped backups

### Safety & Reliability
- **Automatic Backups** - Every file modification creates a timestamped backup
- **Line Ending Preservation** - Maintains original file line ending styles (CRLF, LF, CR)
- **Context Validation** - Verifies patch context matches target files
- **Error Recovery** - Comprehensive error handling with detailed logging

### User Experience
- **Batch Processing** - Handle multiple files efficiently with "Next Pending" navigation
- **Progress Tracking** - Visual indicators show completion status for all files
- **Persistent Configuration** - Remembers your default project directory
- **Comprehensive Logging** - Timestamped activity log with color-coded messages
- **Flexible UI** - Resizable panes and comprehensive menu system

## Requirements

- **Python**: 3.7+ (tested extensively with Python 3.12)
- **Platforms**: Windows 10/11, macOS, Linux
- **Dependencies**: None - uses only Python standard library (tkinter)

## Installation

### Download and Run
```bash
# Download the single Python file
curl -O https://raw.githubusercontent.com/your-username/gritty-diff-gui-patcher/main/diff_gui_patcher.py

# Run directly
python diff_gui_patcher.py
```

### Make Executable (Unix/Linux/macOS)
```bash
chmod +x diff_gui_patcher.py
./diff_gui_patcher.py
```

## Quick Start

1. **Set Project Root** - Browse to your project directory (saved as default for future use)
2. **Paste Diff** - Copy unified diff content into the text area
3. **Process Diff** - Click "Process Diff" to parse files and hunks
4. **Apply Patches** - For each file:
   - Select from the file list
   - Click "AUTO EDIT" to apply changes (creates backup)
   - Click "VERIFY" to confirm correctness
   - Use "UNDO" if rollback is needed
5. **Navigate Efficiently** - Use "Next Pending" to jump between unprocessed files

## Advanced Usage

### Menu Features
- **File Menu**: Set project root, reset default directory
- **Edit Menu**: Clear diff input, reset all processing state
- **View Menu**: Refresh directory tree, clear activity log
- **Help Menu**: About dialog, configuration file location

### Batch Operations
The application tracks the status of each file:
- ⏳ **Pending** - Not yet processed
- ✎ **Edited** - Changes applied, awaiting verification
- ✅ **Verified** - Successfully applied and confirmed
- ❌ **Failed** - Verification failed

### Configuration Management
Settings are automatically saved to:
- **Linux/macOS**: `~/.diff_gui_patcher_config.json`
- **Windows**: `%USERPROFILE%\.diff_gui_patcher_config.json`

## Use Cases

### Development Workflows
- **Code Reviews** - Apply reviewer suggestions from diff format
- **Patch Distribution** - Share and apply changes across team members
- **API Updates** - Handle large-scale refactoring with confidence
- **Cherry-picking** - Apply specific changes from larger diffs

### Learning & Experimentation
- **Patch Education** - Visual feedback helps understand how patches work
- **Safe Testing** - Automatic backups enable risk-free experimentation
- **Change Analysis** - Color-coded diff display shows exactly what changes

## Technical Details

### Diff Parsing
- Supports standard unified diff format (git diff, svn diff, etc.)
- Handles multiple files with multiple hunks per file
- Parses hunk headers (`@@ -l,s +l,s @@` format)
- Merges duplicate entries for the same file
- Strips common prefixes (`a/`, `b/`) from paths

### Patch Application Algorithm
- Preserves original line endings (CRLF, LF, CR)
- Validates context lines before applying changes
- Handles additions, deletions, and context preservation
- Maintains file encoding using `utf-8` with `surrogateescape` error handling
- Creates binary-accurate output files

### Safety Mechanisms
- **Pre-flight Checks** - Validates target files exist before modification
- **Atomic Operations** - Backup creation before any file modification
- **Content Verification** - Compares expected vs actual results post-patch
- **Rollback Capability** - Restore from timestamped backups
- **Error Isolation** - Failed patches don't affect other files

## Troubleshooting

### Common Issues
- **File Not Found** - Ensure project root is set correctly
- **Permission Denied** - Check file/directory write permissions
- **Malformed Diff** - Verify diff format is standard unified diff
- **Verification Failed** - Check for manual edits after patch application

### Configuration Issues
If configuration saving fails, the application continues with in-memory settings. Check the Help menu for config file location and permissions.

## Development

### Architecture
- **Single File Design** - ~800 lines, maximum portability
- **Modular Structure** - Clear separation of parsing, UI, and file operations
- **Error Handling** - Comprehensive exception handling throughout
- **Cross-platform** - Tested on multiple operating systems

### Key Components
- `Config` class manages persistent settings
- `PatchFile` and `Hunk` dataclasses model diff structure
- `parse_unified_diff()` handles diff parsing
- `apply_hunks_to_text()` performs patch application
- `DiffGuiApp` provides the Tkinter interface

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-username/gritty-diff-gui-patcher.git
cd gritty-diff-gui-patcher

# Run directly - no dependencies to install
python diff_gui_patcher.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Python's `tkinter` for maximum compatibility
- Inspired by traditional patch tools but designed for modern workflows
- Thanks to the Python community for excellent standard library support
