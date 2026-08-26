"""Show a native IMG/XML picker in an isolated process."""

from __future__ import annotations

import os
import subprocess
import sys


def _pick_osascript(kind: str, initial: str) -> str:
    """Use macOS AppleScript native file dialog (no dependencies)."""
    if kind == "img":
        prompt = "选择 IMG 文件"
    else:
        prompt = "选择 IMG.XML 文件"

    default_loc = ""
    if initial and os.path.isdir(initial):
        default_loc = f' default location POSIX file "{initial}"'

    # Ask for a file with no type restriction (IMG/XML have no UTI)
    script = (
        f'set f to choose file with prompt "{prompt}"{default_loc}\n'
        f"POSIX path of f"
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # User cancelled — not an error
        stderr = result.stderr.strip()
        if "User canceled" in stderr or "User cancelled" in stderr:
            return ""
        raise RuntimeError(stderr or "osascript file picker failed")
    return result.stdout.strip()


def _pick_tkinter(kind: str, initial: str) -> str:
    """Fallback: use tkinter file dialog."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.update()
    if kind == "img":
        title = "选择 IMG 文件"
        filetypes = [("IMG files", "*.img"), ("All files", "*.*")]
    else:
        title = "选择 IMG.XML 文件"
        filetypes = [("IMG XML files", "*.img.xml"), ("XML files", "*.xml")]
    path = filedialog.askopenfilename(
        parent=root,
        initialdir=initial or None,
        title=title,
        filetypes=filetypes,
    )
    root.destroy()
    return path


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("img", "xml"):
        print("usage: _file_picker <img|xml> [initial_dir]", file=sys.stderr)
        return 2
    kind = sys.argv[1]
    initial = sys.argv[2] if len(sys.argv) > 2 else ""

    # macOS: prefer osascript (zero dependencies, always available)
    if sys.platform == "darwin":
        try:
            path = _pick_osascript(kind, initial)
            if path:
                sys.stdout.write(path)
            return 0
        except RuntimeError as exc:
            print(f"osascript picker failed: {exc}", file=sys.stderr)
            return 3

    # Other platforms: try tkinter
    try:
        path = _pick_tkinter(kind, initial)
    except ImportError as exc:
        print(f"tkinter not available: {exc}", file=sys.stderr)
        return 3

    if path:
        sys.stdout.write(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
