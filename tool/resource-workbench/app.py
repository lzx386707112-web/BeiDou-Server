#!/usr/bin/env python3
"""Unified launcher for BeiDou's local IMG resource tools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
WZPY_ROOT = REPO_ROOT / "tool" / "wz-python"
MIGRATION_ROOT = REPO_ROOT / "tool" / "scripts" / "migration"


def create_app():
    for path in (HERE, WZPY_ROOT, MIGRATION_ROOT):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    if not (MIGRATION_ROOT / "migrate_arcane_river_expansion.py").is_file():
        raise FileNotFoundError(
            f"缺少工作台依赖: {MIGRATION_ROOT / 'migrate_arcane_river_expansion.py'}"
        )

    from map_mob.app import app as map_mob_app
    from img_editor.app import create_app as create_img_editor
    from quest_manager.app import app as quest_manager_app
    from item_manager.app import app as item_manager_app
    from skill_manager.app import app as skill_manager_app

    shell = Flask(
        __name__,
        template_folder=str(HERE / "templates"),
        static_folder=str(HERE / "static"),
        static_url_path="/workbench-static",
    )

    @shell.get("/")
    def index():
        module = request.args.get("module", "map-mob")
        if module not in ("map-mob", "img-editor", "quests", "items", "skills"):
            module = "map-mob"
        return render_template("index.html", initial_module=module)

    @shell.get("/api/health")
    def health():
        return jsonify({
            "ok": True,
            "name": "BeiDou Resource Workbench",
            "modules": ["map-mob", "img-editor", "quests", "items", "skills"],
        })

    return DispatcherMiddleware(shell, {
        "/map-mob": map_mob_app,
        "/img-editor": create_img_editor(),
        "/quests": quest_manager_app,
        "/items": item_manager_app,
        "/skills": skill_manager_app,
    })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    run_simple(args.host, args.port, create_app(), threaded=True, use_reloader=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
