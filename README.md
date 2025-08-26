# Diff GUI Patcher

A single-file Python GUI tool for applying unified diff patches to your projects with visual feedback and safety features.

## What it does

Takes unified diffs (like `git diff` output) and applies them to your files through an easy-to-use graphical interface. No more wrestling with command-line patch tools or manually editing files.

## Key Features

- **Visual file browser** - Navigate your project structure
- **Safe patching** - Automatic backups before any changes  
- **Verification system** - Confirms patches applied correctly
- **One-click undo** - Restore from backups if needed
- **Batch processing** - Handle multiple files in sequence
- **Progress tracking** - See what's done and what's pending
- **Persistent settings** - Remembers your default project directory

## Requirements

- Python 3.7+ (tested with Python 3.12)
- Windows 10/11, macOS, or Linux
- No external dependencies - uses only Python standard library

## Installation

1. Download `diff_gui_patcher.py`
2. Run with: `python diff_gui_patcher.py`

## Usage

1. **Set project root** - Choose your project directory
2. **Paste diff** - Copy/paste a unified diff into the text area
3. **Process diff** - Click "Process Diff" to parse the changes
4. **Apply patches** - For each file:
   - Select file from list
   - Click "AUTO EDIT" to apply changes (creates backup)
   - Click "VERIFY" to confirm it worked
   - Use "UNDO" if you need to revert
5. **Navigate efficiently** - Use "Next Pending" to jump between files

## Use Cases

- Applying code review suggestions
- Distributing patches across team members  
- Large-scale refactoring or API updates
- Learning how patches work with visual feedback
- Safe experimentation with automatic rollback

## Technical Notes

- Single Python file (~800 lines) for maximum portability
- Automatic timestamped backups before any file modification
- Handles standard git diff format with multiple files and hunks
- Cross-platform file handling with proper encoding support
- Configuration persisted in user home directory

## Safety Features

Every file modification creates an automatic backup with timestamp. The verification system confirms changes match expected results. One-click undo restores from the most recent backup. All operations are logged with timestamps for audit trail.
