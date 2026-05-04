# CodeBuster — Plagiarism Detection for Coding Assignments

A standalone desktop application that detects suspicious similarity between
student coding submissions. Powered by Python + PyQt6.

---

## Features

- **Multi-file scanning** – specify one or more target filenames or extensions;
  all matching files under the submission root are discovered and pairwise-compared.
- **Normalisation** – comments, whitespace and variable names are stripped so
  only code structure is compared (Java, Python, C#, and JavaScript-family
  files built-in; extensible).
- **Results table** – sortable by any column; filterable by keyword in folder
  names or by minimum similarity percentage.
- **Side-by-side diff viewer** – two synchronised scrolling panes with
  matching regions highlighted in yellow and unique regions in red.
  Toggle between the original source and the normalised comparison file.
- **Statistics page** – mean, median, min, max similarity; per-file line /
  word / character counts; similarity histogram; configurable threshold counter.
- **Persistent data** – all results stored in `codebuster.db` (SQLite) in the
  current directory; reloaded automatically on next launch.

---

## Running from source

CodeBuster is a Python desktop application. If you are running it from source,
create a virtual environment first so the PyQt6 and project dependencies are
installed for this project only.

### Linux

```bash
# 1. From the project root, create a virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Launch CodeBuster
python main.py
```

If `python3 -m venv` is not available, install your distribution's venv package
first, for example `sudo apt install python3-venv` on Debian or Ubuntu.

### Windows

```powershell
# 1. From the project root, create a virtual environment
py -3.11 -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Launch CodeBuster
python main.py
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the virtual environment again.

When you are finished, run `deactivate` to leave the virtual environment.

---

## Building a standalone executable

PyInstaller must be run **on each target OS** separately. There is no
cross-compilation — the executable produced on Linux will only run on Linux.

### Prerequisites

```bash
pip install pyinstaller
```

### Build

```bash
# From the project root directory:
pyinstaller codebuster.spec
```

The executable is written to `dist/CodeBuster` (Linux/macOS) or
`dist/CodeBuster.exe` (Windows).

### Platform notes

| Platform | Notes |
|----------|-------|
| **Linux**   | Requires a display server (X11 or Wayland). No extra steps. |
| **Windows** | Run the build on a Windows machine. The `.exe` is self-contained. |
| **macOS**   | Run the build on macOS. You may need to allow the app in *System Settings → Privacy & Security* on first launch. To create a `.app` bundle add `--windowed` to the spec's `EXE` call (already set). |

---

## Adding support for a new language

1. Create `core/normalizer/<language>.py` implementing `BaseNormalizer`.
2. Set `extensions = ['.ext']` on the class.
3. Register it in `core/normalizer/base.py` → `get_normalizer()`.

Scans can target exact filenames such as `MergeRuns.java` or file types such as
`.py`, `py`, `.cs`, `cs`, `.js`, `jsx`, or `tsx`.

---

## Project layout

```
codebuster/
├── main.py                   Entry point
├── requirements.txt
├── codebuster.spec           PyInstaller build spec
├── core/
│   ├── scanner.py            File discovery
│   ├── comparator.py         Normalise + pairwise compare
│   ├── database.py           SQLite persistence
│   └── normalizer/
│       ├── base.py           Abstract base + registry
│       ├── csharp.py         C# normaliser
│       ├── java.py           Java normaliser
│       ├── javascript.py     JavaScript / TypeScript normaliser
│       └── python_lang.py    Python normaliser
└── gui/
    ├── main_window.py        Main window + menus
    ├── scan_tab.py           Scan tab + background worker
    ├── results_tab.py        Results table with filtering
    ├── diff_viewer.py        Side-by-side diff with highlighting
    └── stats_tab.py          Statistics + histogram
```
