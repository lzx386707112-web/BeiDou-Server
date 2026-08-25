"""Show a native IMG/XML picker in an isolated process."""

from __future__ import annotations

import sys


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("img", "xml"):
        print("usage: _file_picker <img|xml> [initial_dir]", file=sys.stderr)
        return 2
    kind = sys.argv[1]
    initial = sys.argv[2] if len(sys.argv) > 2 else ""

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        print(f"tkinter not available: {exc}", file=sys.stderr)
        return 3

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
    if path:
        sys.stdout.write(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
