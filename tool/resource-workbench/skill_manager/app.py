from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import Flask, jsonify, render_template, request, send_file

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WZPY_ROOT = ROOT / "tool" / "wz-python"
if str(WZPY_ROOT) not in sys.path:
    sys.path.insert(0, str(WZPY_ROOT))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzKey,
    WzRawDataProperty,
    WzSoundProperty,
    WzSubProperty,
    WzUolProperty,
    detect_region_from_img,
)
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.incremental_img import mutate_img, scan_img  # noqa: E402
from wzpy.incremental_xml import mutate_xml  # noqa: E402
from wzpy.properties import WzVideoProperty  # noqa: E402

TMS_ROOT = ROOT.parent / "TMS"
TMS_DATA = TMS_ROOT / "MapleStory-IMG" / "Data"
MS_PACKS = TMS_ROOT / "MapleStory" / "Data" / "Packs"
MS_PROBE = TMS_ROOT / "black_mage_report_tools" / "ms_probe" / "bin" / "Debug" / "net8.0" / "MSProbe.dll"
MS_CACHE_ROOT = TMS_ROOT / "ms-extract"
CLIENT_SKILL = ROOT / "clien" / "Data" / "Skill"
SERVER_SKILL = ROOT / "gms-server" / "wz" / "Skill.wz"
ZH_STRING = ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Skill.img.xml"
SERVER_STRING = ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml"
BACKUP_ROOT = ROOT / ".workbuddy" / "resource-workbench-backups" / "skills"
GMS_KEY = WzKey.for_region("GMS")
_CANVAS_OUTLINK = re.compile(r"(?:^|/)Skill/_Canvas/([^/]+)\.img/(.+)$", re.IGNORECASE)
EDITABLE_TYPES = {"Short", "Int", "Long", "Float", "Double", "String", "Vector", "UOL"}
COPYABLE_TYPES = EDITABLE_TYPES | {"SubProperty", "Null"}
ANIMATION_SKIP = {
    "icon", "iconDisabled", "iconMouseOver", "iconMouseover", "level", "req", "action",
    "info", "common", "PVPcommon", "psd", "invisible", "masterLevel", "skillType",
    "elemAttr", "weapon", "subWeapon", "disable", "notRemoved", "timeLimited",
}
_WRITE_LOCK = threading.RLock()
_MS_INDEX_LOCK = threading.Lock()

JOB_NAMES = {
    0: "初心者", 100: "战士", 110: "剑客", 111: "勇士", 112: "英雄",
    120: "准骑士", 121: "骑士", 122: "圣骑士", 130: "枪战士", 131: "龙骑士", 132: "黑骑士",
    200: "魔法师", 210: "法师(火毒)", 211: "魔法师(火毒)", 212: "大魔导师(火毒)",
    220: "法师(冰雷)", 221: "魔法师(冰雷)", 222: "大魔导师(冰雷)",
    230: "牧师", 231: "祭司", 232: "主教",
    300: "弓箭手", 310: "猎人", 311: "射手", 312: "箭神", 320: "弩弓手", 321: "游侠", 322: "神射手",
    400: "飞侠", 410: "刺客", 411: "无影人", 412: "夜使者", 420: "侠客", 421: "独行客", 422: "暗影神偷",
    500: "海盗", 510: "拳手", 511: "斗士", 512: "冲锋队长", 520: "枪手", 521: "大副", 522: "船长",
    1000: "初心者(骑士团)", 1100: "魂骑士", 1110: "魂骑士", 1111: "魂骑士", 1112: "魂骑士",
    1200: "炎术士", 1210: "炎术士", 1211: "炎术士", 1212: "炎术士",
    1300: "风行者", 1310: "风行者", 1311: "风行者", 1312: "风行者",
    1400: "夜行者", 1410: "夜行者", 1411: "夜行者", 1412: "夜行者",
    1500: "奇袭者", 1510: "奇袭者", 1511: "奇袭者", 1512: "奇袭者",
    2000: "战神(初心者)", 2100: "战神", 2110: "战神", 2111: "战神", 2112: "战神",
    2200: "龙神(初心者)", 2210: "龙神", 2211: "龙神", 2212: "龙神", 2213: "龙神",
    2214: "龙神", 2215: "龙神", 2216: "龙神", 2217: "龙神", 2218: "龙神",
    3000: "双弩精灵(初心者)", 3100: "双弩精灵", 3110: "双弩精灵", 3111: "双弩精灵", 3112: "双弩精灵",
    4000: "幻影(初心者)", 4100: "幻影", 4110: "幻影", 4111: "幻影", 4112: "幻影",
    5000: "隐月(初心者)", 5100: "隐月", 5110: "隐月", 5111: "隐月", 5112: "隐月",
    800: "管理员", 900: "骑士团", 910: "隐藏技能",
    40000: "五转通用", 40001: "五转战士", 40002: "五转法师", 40003: "五转弓手",
    40004: "五转飞侠", 40005: "五转海盗",
}

app = Flask(__name__, template_folder=str(HERE / "templates"), static_folder=str(HERE / "static"))


def _ok(**payload):
    return jsonify({"ok": True, **payload})


@app.errorhandler(Exception)
def _error(exc: Exception):
    status = 404 if isinstance(exc, (FileNotFoundError, KeyError)) else 400
    return jsonify({"ok": False, "reason": str(exc).strip("'")}), status


def _book(raw: Any) -> str:
    value = str(raw or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValueError("职业技能书无效")
    return value


def _skill_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not re.fullmatch(r"\d+", value):
        raise ValueError("技能 ID 必须是数字")
    return str(int(value))


def _job_group(book: str) -> str:
    if not book.isdigit():
        return "其他"
    job_id = int(book)
    if job_id >= 800000:
        return "五转技能"
    if 40000 <= job_id < 50000:
        return "五转"
    if 50000 <= job_id < 60000:
        return "六转"
    if job_id < 1000:
        return "冒险家"
    if job_id < 2000:
        return "皇家骑士团"
    if job_id in {2000} or 2100 <= job_id < 2200:
        return "战神"
    if job_id in {2001} or 2200 <= job_id < 2300:
        return "龙神"
    if job_id in {2002} or 2300 <= job_id < 2400:
        return "双弩精灵"
    if job_id in {2003} or 2400 <= job_id < 2500:
        return "幻影"
    if job_id in {2005} or 2500 <= job_id < 2600:
        return "隐月"
    if job_id in {2004} or 2700 <= job_id < 2800:
        return "夜光"
    if job_id < 3000:
        return "英雄职业"
    if job_id in {3001} or 3100 <= job_id < 3200:
        return "恶魔"
    if 3200 <= job_id < 3300:
        return "爆破手"
    if 3300 <= job_id < 3400:
        return "弩豹游侠"
    if job_id in {3002} or 3500 <= job_id < 3700:
        return "尖兵"
    if job_id < 4000:
        return "反抗者"
    if job_id in {4001} or 4100 <= job_id < 4200:
        return "剑豪"
    if job_id in {4002} or 4200 <= job_id < 4300:
        return "阴阳师"
    if job_id < 5000:
        return "晓之阵"
    if job_id < 6000:
        return "米哈逸"
    if job_id in {6001} or 6500 <= job_id < 6600:
        return "天使破坏者"
    if job_id in {6003} or 6300 <= job_id < 6400:
        return "凯殷"
    if job_id < 7000:
        return "超新星"
    if 10000 <= job_id < 11000:
        return "神之子"
    if 14000 <= job_id < 15000:
        return "超能力者"
    if 15000 <= job_id < 16000:
        return "阿戴尔 / 伊利恩 / 亚克"
    if 16000 <= job_id < 17000:
        return "阿尼玛"
    if 17000 <= job_id < 18000:
        return "墨玄 / 琳恩"
    if 12000 <= job_id < 14000:
        return "活动职业"
    return "其他"


def _job_name(book: str, book_names: dict[str, str]) -> str:
    if book in book_names:
        return book_names[book]
    if book.isdigit() and int(book) in JOB_NAMES:
        return JOB_NAMES[int(book)]
    return f"技能书 {book}"


def _client_path(book: str) -> Path:
    return CLIENT_SKILL / f"{book}.img"


def _server_path(book: str) -> Path:
    return SERVER_SKILL / f"{book}.img.xml"


def _tms_img_path(book: str) -> Path:
    return TMS_DATA / "Skill" / f"{book}.img"


def _tms_canvas_path(book: str) -> Path:
    return TMS_DATA / "Skill" / "_Canvas" / f"{book}.img"


def _tms_string_path() -> Path:
    return TMS_DATA / "String" / "Skill.img"


def _natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


@lru_cache(maxsize=24)
def _cached_image(path_text: str, region: str, mtime_ns: int, size: int) -> WzImage:
    del mtime_ns, size
    path = Path(path_text)
    data = path.read_bytes()
    chosen = region or detect_region_from_img(data) or "BMS"
    image = WzImage.from_bytes(data, key=WzKey.for_region(chosen), name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise ValueError(f"IMG 解析失败: {path.name}: {image.parse_warnings}")
    return image


def _load_image(path: Path, region: str | None = None) -> WzImage:
    if not path.is_file():
        raise FileNotFoundError(f"IMG 不存在: {path}")
    stat = path.stat()
    return _cached_image(str(path.resolve()), region or "", stat.st_mtime_ns, stat.st_size)


def _skill_node(image: WzImage, skill_id: str):
    parents = []
    skills = image.root.child("skill")
    if isinstance(skills, WzSubProperty):
        parents.append(skills)
    parents.append(image.root)
    names = (skill_id, skill_id.zfill(7), skill_id.zfill(8))
    for parent in parents:
        for name in names:
            node = parent.child(name)
            if node is not None:
                return node
        for node in parent.children():
            if node.name.isdigit() and str(int(node.name)) == skill_id:
                return node
    raise KeyError(f"技能记录不存在: {skill_id}")


def _scalar_value(node) -> Any:
    if node.type_name == "Vector":
        return {"x": int(node.x), "y": int(node.y)}
    if isinstance(node, WzCanvasProperty):
        return {
            "width": int(node.width), "height": int(node.height),
            "format": int(node.format), "format2": int(node.format2),
            "linked": bool(node.child("_outlink") or node.child("_inlink")),
        }
    if isinstance(node, WzSubProperty):
        return {"children": node.child_count()}
    if isinstance(node, (WzRawDataProperty, WzSoundProperty, WzVideoProperty)):
        return {"bytes": int(getattr(node, "_data_length", 0))}
    value = getattr(node, "value", None)
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


def _walk_nodes(root) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(parent, prefix: tuple[str, ...]) -> None:
        for child in parent.children():
            path = (*prefix, child.name)
            rows.append({
                "path": "/".join(path), "name": child.name, "type": child.type_name,
                "value": _scalar_value(child), "depth": len(path) - 1,
                "container": isinstance(child, WzSubProperty),
                "editable": child.type_name in EDITABLE_TYPES,
            })
            if hasattr(child, "children"):
                visit(child, path)

    visit(root, ())
    return rows


def _diff(local_rows: list[dict[str, Any]], tms_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    local = {row["path"]: row for row in local_rows}
    tms = {row["path"]: row for row in tms_rows}
    result = []
    for path in sorted(set(local) | set(tms), key=lambda value: (value.count("/"), value)):
        left, right = local.get(path), tms.get(path)
        status = "localOnly" if right is None else "tmsOnly" if left is None else "same"
        if left is not None and right is not None and (left["type"], left["value"]) != (right["type"], right["value"]):
            status = "changed"
        result.append({"path": path, "status": status, "local": left, "tms": right})
    return result


@lru_cache(maxsize=4)
def _string_catalog(path_text: str, mtime_ns: int, size: int) -> tuple[dict[str, str], dict[str, str]]:
    del mtime_ns, size
    path = Path(path_text)
    names: dict[str, str] = {}
    books: dict[str, str] = {}
    if not path.is_file():
        return names, books
    root = ET.parse(path).getroot()
    for node in root:
        key = node.get("name", "")
        values = {child.get("name"): child.get("value", "") for child in node}
        if "bookName" in values:
            books[str(int(key)) if key.isdigit() else key] = values["bookName"]
        elif key.isdigit():
            names[str(int(key))] = values.get("name", "")
    return names, books


def _strings() -> tuple[dict[str, str], dict[str, str]]:
    for path in (ZH_STRING, SERVER_STRING):
        if path.is_file():
            stat = path.stat()
            return _string_catalog(str(path), stat.st_mtime_ns, stat.st_size)
    return {}, {}


@lru_cache(maxsize=4)
def _tms_string_catalog(path_text: str, mtime_ns: int, size: int) -> tuple[dict[str, str], dict[str, str]]:
    del mtime_ns, size
    names: dict[str, str] = {}
    books: dict[str, str] = {}
    path = Path(path_text)
    if not path.is_file():
        return names, books
    image = _load_image(path, "BMS")
    for child in image.root.children():
        book_name = child.child("bookName") if hasattr(child, "child") else None
        skill_name = child.child("name") if hasattr(child, "child") else None
        key = str(int(child.name)) if child.name.isdigit() else child.name
        if book_name is not None and getattr(book_name, "value", ""):
            books[key] = str(book_name.value)
        if skill_name is not None and getattr(skill_name, "value", ""):
            names[key] = str(skill_name.value)
    return names, books


def _tms_strings() -> tuple[dict[str, str], dict[str, str]]:
    path = _tms_string_path()
    if not path.is_file():
        return {}, {}
    stat = path.stat()
    return _tms_string_catalog(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _merged_strings() -> tuple[dict[str, str], dict[str, str]]:
    tms_names, tms_books = _tms_strings()
    local_names, local_books = _strings()
    names = dict(tms_names)
    names.update({key: value for key, value in local_names.items() if value})
    books = dict(tms_books)
    books.update(local_books)
    return names, books


@lru_cache(maxsize=4)
def _ms_skill_index_cached(signature: tuple[tuple[str, int, int], ...]) -> dict[str, Path]:
    if not signature or not MS_PROBE.is_file():
        return {}
    dotnet = shutil.which("dotnet")
    if not dotnet:
        return {}
    output: dict[str, Path] = {}
    for pack_text, _mtime, _size in signature:
        pack = Path(pack_text)
        result = subprocess.run(
            [dotnet, str(MS_PROBE), str(pack), str(MS_CACHE_ROOT), "--list"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            continue
        for line in result.stdout.splitlines():
            match = re.fullmatch(r"Skill/([^/]+)\.img", line.strip(), re.IGNORECASE)
            if match:
                output.setdefault(match.group(1), pack)
    return output


def ms_pack_signature() -> tuple[tuple[str, int, int], ...]:
    if not MS_PACKS.is_dir():
        return ()
    return tuple(
        (str(path), path.stat().st_mtime_ns, path.stat().st_size)
        for path in sorted(MS_PACKS.glob("Skill_*.ms"))
    )


def ms_skill_index() -> dict[str, Path]:
    with _MS_INDEX_LOCK:
        return _ms_skill_index_cached(ms_pack_signature())


def _ms_cache_books() -> dict[str, Path]:
    found: dict[str, Path] = {}
    if not MS_CACHE_ROOT.is_dir():
        return found
    candidates = list(MS_CACHE_ROOT.glob("Skill_*.img"))
    try:
        for folder in MS_CACHE_ROOT.iterdir():
            if folder.is_dir():
                candidates.extend(folder.glob("Skill_*.img"))
    except OSError:
        pass
    for path in candidates:
        book = path.stem.removeprefix("Skill_")
        if book:
            found.setdefault(book, path)
    return found


def _extracted_ms_path(book: str, pack: Path | None = None) -> Path | None:
    names = (f"Skill_{book}.img", f"{book}.img")
    roots = [MS_CACHE_ROOT]
    if pack is not None:
        roots.insert(0, MS_CACHE_ROOT / pack.stem)
    for root in roots:
        if not root.is_dir():
            continue
        for name in names:
            for candidate in (root / name, root / pack.stem / name if pack else root / name):
                if candidate.is_file():
                    return candidate
        try:
            for child in root.iterdir():
                if child.is_dir():
                    for name in names:
                        candidate = child / name
                        if candidate.is_file():
                            return candidate
        except OSError:
            continue
    return None


def extract_ms_skill(book: str) -> tuple[Path, Path] | None:
    cached = _extracted_ms_path(book)
    if cached is not None:
        return cached, cached.parent
    pack = ms_skill_index().get(book)
    cached = _extracted_ms_path(book, pack)
    if pack is None:
        return (cached, cached.parent) if cached is not None else None
    target_dir = MS_CACHE_ROOT / pack.stem
    target = target_dir / f"Skill_{book}.img"
    if cached is not None and cached.stat().st_mtime_ns >= pack.stat().st_mtime_ns:
        return cached, pack
    if not MS_PROBE.is_file():
        raise ValueError(f"MSProbe 不存在: {MS_PROBE}")
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise ValueError("找不到 dotnet，无法读取 TMS MS 包")
    MS_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".skill-extract-", dir=MS_CACHE_ROOT) as directory:
        result = subprocess.run(
            [dotnet, str(MS_PROBE), str(pack), directory, f"Skill/{book}.img"],
            capture_output=True, text=True, check=False,
        )
        extracted = Path(directory) / f"Skill_{book}.img"
        if result.returncode != 0 or not extracted.is_file():
            raise ValueError(
                f"无法从 {pack.name} 提取 {book}: {result.stderr.strip() or result.stdout.strip()}"
            )
        data = extracted.read_bytes()
        _load_image(extracted)
        target_dir.mkdir(parents=True, exist_ok=True)
        fd, raw = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target_dir)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw, target)
    return target, pack


def _source_paths(book: str) -> dict[str, dict[str, Any]]:
    local = _client_path(book)
    tms_img = _tms_img_path(book)
    tms_canvas = _tms_canvas_path(book)
    cached = _extracted_ms_path(book)
    return {
        "local": {"exists": local.is_file(), "path": str(local), "label": "本地 IMG", "pack": None},
        "tms": {"exists": tms_img.is_file(), "path": str(tms_img), "label": "TMS IMG", "pack": None},
        "canvas": {"exists": tms_canvas.is_file(), "path": str(tms_canvas), "label": "TMS _Canvas", "pack": None},
        "ms": {
            "exists": cached is not None,
            "path": str(cached) if cached else "",
            "label": f"TMS MS · {cached.parent.name}" if cached else "TMS MS",
            "pack": cached.parent.name if cached else None,
            "error": None,
        },
    }


def _img_stems(folder: Path) -> set[str]:
    if not folder.is_dir():
        return set()
    return {path.stem for path in folder.glob("*.img")}


def _local_books() -> set[str]:
    return _img_stems(CLIENT_SKILL)


def _tms_books() -> set[str]:
    names = _img_stems(TMS_DATA / "Skill")
    names.update(_ms_cache_books())
    names.update(ms_skill_index())
    return names


def _books(side: str = "all") -> set[str]:
    if side == "local":
        return _local_books()
    if side == "tms":
        return _tms_books()
    return _local_books() | _tms_books()


def _skill_ids_from_image(path: Path, region: str | None = None) -> list[str]:
    image = _load_image(path, region)
    skills = image.root.child("skill")
    if isinstance(skills, WzSubProperty):
        return [str(int(child.name)) if child.name.isdigit() else child.name for child in skills.children()]
    return [
        str(int(child.name)) if child.name.isdigit() else child.name
        for child in image.root.children() if child.name.isdigit()
    ]


@lru_cache(maxsize=256)
def _cached_skill_ids(path_text: str, region: str, mtime_ns: int, size: int) -> tuple[str, ...]:
    del mtime_ns, size
    try:
        return tuple(_skill_ids_from_image(Path(path_text), region or None))
    except Exception:
        return ()


def _ids_for_path(path: Path, region: str) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    stat = path.stat()
    return _cached_skill_ids(str(path), region, stat.st_mtime_ns, stat.st_size)


def _source_file(book: str, source: str) -> tuple[Path, str]:
    if source == "local":
        path = _client_path(book)
        if not path.is_file():
            raise FileNotFoundError("本地技能书不存在")
        return path, "GMS"
    if source == "tms":
        path = _tms_img_path(book)
        if not path.is_file():
            raise FileNotFoundError("TMS IMG 不存在")
        return path, "BMS"
    if source == "canvas":
        path = _tms_canvas_path(book)
        if not path.is_file():
            raise FileNotFoundError("TMS _Canvas 不存在")
        return path, "BMS"
    if source == "ms":
        extracted = extract_ms_skill(book)
        if extracted is None:
            raise FileNotFoundError("TMS MS 中没有这份技能书")
        return extracted[0], "BMS"
    raise ValueError("资源来源无效")


def _preferred_tms_source(book: str) -> str | None:
    sources = _source_paths(book)
    for key in ("tms", "ms"):
        if sources[key]["exists"]:
            return key
    return None


def _detail(book: str, skill_id: str, source: str) -> dict[str, Any] | None:
    try:
        path, region = _source_file(book, source)
        image = _load_image(path, region)
        node = _skill_node(image, skill_id)
    except (FileNotFoundError, KeyError, ValueError):
        return None
    names, _books = _merged_strings()
    rows = _walk_nodes(node)
    size = path.stat().st_size
    digest = ""
    if size < 2_000_000:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "scope": source, "book": book, "id": skill_id, "name": names.get(skill_id, ""),
        "file": str(path), "record": node.name, "nodes": rows,
        "sha256": digest,
        "mutable": source == "local",
    }


def _max_level(node) -> int:
    level = node.child("level")
    if not isinstance(level, WzSubProperty):
        return 0
    highest = 0
    for child in level.children():
        if child.name.isdigit():
            highest = max(highest, int(child.name))
    return highest


def _frame_delay(node) -> int:
    delay = getattr(node.child("delay"), "value", None) if hasattr(node, "child") else None
    try:
        return max(16, int(delay or 100))
    except (TypeError, ValueError):
        return 100


def _origin(node) -> dict[str, int]:
    origin = node.child("origin") if hasattr(node, "child") else None
    if origin is not None and origin.type_name == "Vector":
        return {"x": int(origin.x), "y": int(origin.y)}
    return {"x": 0, "y": int(getattr(node, "height", 0) or 0)}


def _collect_frames(container, prefix: str) -> list[dict[str, Any]]:
    frames = []
    children = [child for child in container.children() if child.name.isdigit()]
    children.sort(key=lambda node: _natural_key(node.name))
    for child in children:
        if not isinstance(child, (WzCanvasProperty, WzUolProperty)):
            continue
        frames.append({
            "path": f"{prefix}/{child.name}" if prefix else child.name,
            "name": child.name,
            "type": child.type_name,
            "delay": _frame_delay(child),
            "width": int(getattr(child, "width", 0) or 0),
            "height": int(getattr(child, "height", 0) or 0),
            "origin": _origin(child),
            "uol": getattr(child, "value", None) if isinstance(child, WzUolProperty) else None,
        })
    return frames


def _preview_tracks(node) -> list[dict[str, Any]]:
    tracks = []
    icon = node.child("icon")
    if isinstance(icon, WzCanvasProperty):
        tracks.append({
            "name": "icon", "frames": [{
                "path": "icon", "name": "icon", "type": "Canvas", "delay": 1000,
                "width": int(icon.width), "height": int(icon.height), "origin": _origin(icon), "uol": None,
            }],
        })
    for child in node.children():
        if child.name in ANIMATION_SKIP or not isinstance(child, WzSubProperty):
            continue
        direct = _collect_frames(child, child.name)
        if direct:
            tracks.append({"name": child.name, "frames": direct})
            continue
        for nested in child.children():
            if isinstance(nested, WzSubProperty):
                frames = _collect_frames(nested, f"{child.name}/{nested.name}")
                if frames:
                    tracks.append({"name": f"{child.name}/{nested.name}", "frames": frames})
    return tracks


def _follow_canvas_store(node):
    if not isinstance(node, WzCanvasProperty):
        return None
    for key in ("_outlink", "_inlink"):
        link = node.child(key)
        if link is None:
            continue
        raw = str(getattr(link, "value", "")).replace("\\", "/").strip("/")
        match = _CANVAS_OUTLINK.search(raw)
        if match is None:
            continue
        store = _tms_canvas_path(match.group(1))
        if not store.is_file():
            continue
        image = _load_image(store, "BMS")
        target = image.root.get(match.group(2).strip("/"))
        if isinstance(target, WzCanvasProperty):
            return target, image, store, "BMS"
    return None


def _resolve_canvas(node, image: WzImage):
    if isinstance(node, WzUolProperty) and node.parent is not None:
        target = node.parent.get(str(node.value))
        if target is None:
            raise ValueError(f"无法解析 UOL: {node.value}")
        node = target
    if not isinstance(node, WzCanvasProperty):
        raise ValueError("节点不是 Canvas")
    followed = _follow_canvas_store(node)
    if followed is not None:
        return followed[0]
    for key in ("_inlink", "_outlink"):
        link = node.child(key)
        if link is None:
            continue
        raw = str(getattr(link, "value", "")).replace("\\", "/").strip("/")
        parts = [part for part in raw.split("/") if part and part not in {image.name, "Skill"}]
        target = image.root.get("/".join(parts)) or image.root.get(raw)
        if isinstance(target, WzCanvasProperty):
            return target
    return node


def _decode_node_canvas(node, image: WzImage, path: Path, region: str):
    del path
    followed = _follow_canvas_store(node) if isinstance(node, WzCanvasProperty) else None
    if followed is not None:
        canvas, _store_image, _store, store_region = followed
        return decode_canvas(canvas, region=store_region)
    canvas = _resolve_canvas(node, image)
    try:
        return decode_canvas(canvas, region=region)
    except Exception:
        fallback = "GMS" if region != "GMS" else "BMS"
        return decode_canvas(canvas, region=fallback)


def _atomic_commit(payloads: dict[Path, bytes]) -> None:
    originals = {path: path.read_bytes() if path.exists() else None for path in payloads}
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    temporaries: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if originals[path] is not None:
                backup = BACKUP_ROOT / ("__".join(path.relative_to(ROOT).parts) + ".bak")
                if not backup.exists():
                    backup.write_bytes(originals[path])
            fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporaries[path] = Path(raw)
        for path, temporary in temporaries.items():
            os.replace(temporary, path)
            replaced.append(path)
    except Exception:
        for path in reversed(replaced):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
    finally:
        for temporary in temporaries.values():
            temporary.unlink(missing_ok=True)


def _raw_top_level(data: bytes, region: str) -> dict[str, bytes]:
    layout = scan_img(data, region=region)
    return {record.name: data[record.start:record.end] for record in layout.root.records}


def _copy_values(node) -> dict[str, Any]:
    kind = node.type_name
    if kind == "Vector":
        return {"x": int(node.x), "y": int(node.y)}
    if kind in {"SubProperty", "Null"}:
        return {}
    value = getattr(node, "value", None)
    return {} if value is None else {"value": value}


def _selected_relatives(paths: list[str] | tuple[str, ...]) -> list[tuple[str, ...]]:
    relatives: list[tuple[str, ...]] = []
    for raw in paths:
        relative = tuple(part for part in str(raw or "").split("/") if part)
        if not relative:
            raise ValueError("不能把整个技能根节点一次性复制进来")
        relatives.append(relative)
    relatives.sort(key=len)
    kept: list[tuple[str, ...]] = []
    for relative in relatives:
        if any(relative[:len(previous)] == previous for previous in kept):
            continue
        kept.append(relative)
    return kept


def _plan_copy_from_tms(
    local_root, tms_root, relatives: tuple[str, ...] | list[tuple[str, ...]], recursive: bool,
) -> list[dict[str, Any]]:
    selected = [relatives] if relatives and isinstance(relatives[0], str) else list(relatives)
    if not selected:
        raise ValueError("没有选择要复制的节点")
    planned = {""}
    planned.update(row["path"] for row in _walk_nodes(local_root))
    ops: list[dict[str, Any]] = []

    def ensure_parent(path: tuple[str, ...]) -> None:
        acc: list[str] = []
        for part in path:
            parent = "/".join(acc)
            acc.append(part)
            key = "/".join(acc)
            if key not in planned:
                ops.append({"operation": "add", "path": parent, "name": part, "kind": "SubProperty", "values": {}})
                planned.add(key)

    def enqueue(node, path: tuple[str, ...], update_existing: bool, descend: bool) -> None:
        kind = node.type_name
        if kind not in COPYABLE_TYPES:
            return
        parent_path = path[:-1]
        if parent_path:
            ensure_parent(parent_path)
        key = "/".join(path)
        parent = "/".join(parent_path)
        if key not in planned:
            ops.append({"operation": "add", "path": parent, "name": path[-1], "kind": kind, "values": _copy_values(node)})
            planned.add(key)
        elif update_existing and kind in EDITABLE_TYPES:
            ops.append({"operation": "edit", "path": key, "kind": kind, "values": _copy_values(node)})
        if descend and kind == "SubProperty":
            for child in node.children():
                enqueue(child, (*path, child.name), False, True)

    for relative in selected:
        target = tms_root.get("/".join(relative))
        if target is None:
            raise KeyError(f"TMS 没有这个节点: {'/'.join(relative)}")
        enqueue(target, relative, True, recursive)
    if not ops:
        raise ValueError("没有可复制的节点（画布等不能增量写入本地）")
    return ops


def _write_skill_ops(book: str, skill_id: str, operations: list[dict[str, Any]]) -> dict[str, Any]:
    client = _client_path(book)
    server = _server_path(book)
    if not client.is_file():
        raise FileNotFoundError("本地技能 IMG 不存在")
    if not operations:
        raise ValueError("没有要执行的节点操作")
    image = _load_image(client, "GMS")
    record = _skill_node(image, skill_id).name
    img_before = client.read_bytes()
    before_top = _raw_top_level(img_before, "GMS")
    img_after = img_before
    xml_after = server.read_text(encoding="utf-8-sig") if server.is_file() else None
    for body in operations:
        operation = str(body.get("operation") or "")
        relative = tuple(part for part in str(body.get("path") or "").split("/") if part)
        if not relative and operation != "add":
            raise ValueError("不能修改技能记录根节点")
        path = ("skill", record, *relative)
        kwargs = {"name": body.get("name"), "kind": body.get("kind"), "values": body.get("values") or {}}
        if operation == "add" and kwargs["kind"] not in COPYABLE_TYPES:
            raise ValueError("不支持新增该节点类型")
        img_after = mutate_img(img_after, operation, path, region="GMS", **kwargs).data
        if xml_after is not None:
            xml_after = mutate_xml(xml_after, operation, path, **kwargs)
    after_top = _raw_top_level(img_after, "GMS")
    for name, raw in before_top.items():
        if name != "skill" and after_top.get(name) != raw:
            raise ValueError(f"未修改的 IMG 记录发生变化: {name}")
    verified = WzImage.from_bytes(img_after, key=GMS_KEY, name=client.name)
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise ValueError("节点修改后的 IMG 解析失败")
    payloads = {client: img_after}
    if xml_after is not None:
        ET.fromstring(xml_after)
        payloads[server] = xml_after.encode()
    _atomic_commit(payloads)
    _cached_skill_ids.cache_clear()
    _cached_image.cache_clear()
    return _detail(book, skill_id, "local")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/jobs")
def jobs():
    side = str(request.args.get("side") or "all")
    if side not in ("all", "local", "tms"):
        raise ValueError("side 只能是 all、local 或 tms")
    _local_names, book_names = _strings()
    pack_index = ms_skill_index() if side != "local" else {}
    ms_cache = _ms_cache_books()
    if side == "tms":
        _tms_skill_names, tms_book_names = _tms_strings()
        names_for_books = dict(book_names)
        names_for_books.update(tms_book_names)
    else:
        names_for_books = book_names
    rows = []
    for book in sorted(_books(side), key=_natural_key):
        local = _client_path(book)
        tms_img = _tms_img_path(book)
        tms_canvas = _tms_canvas_path(book)
        pack = ms_cache.get(book) or pack_index.get(book)
        rows.append({
            "id": book,
            "name": _job_name(book, names_for_books),
            "group": _job_group(book),
            "local": local.is_file(),
            "tms": tms_img.is_file(),
            "canvas": tms_canvas.is_file(),
            "ms": pack is not None,
            "msPack": pack.name if pack is not None else None,
        })
    return _ok(jobs=rows, skillNames=len(_local_names), msReady=bool(ms_cache) or bool(pack_index) or MS_PROBE.is_file(), side=side)


@app.get("/api/skills")
def skills():
    book = _book(request.args.get("job") or request.args.get("book"))
    query = str(request.args.get("q") or "").strip().lower()
    availability = str(request.args.get("availability") or "all")
    side = str(request.args.get("side") or "all")
    if side not in ("all", "local", "tms"):
        raise ValueError("side 只能是 all、local 或 tms")
    local_names, local_books = _strings()
    tms_names, tms_books = ({}, {})
    if side != "local":
        tms_names, tms_books = _tms_strings()
    names = dict(tms_names)
    names.update({key: value for key, value in local_names.items() if value})
    book_names = dict(tms_books)
    book_names.update(local_books)
    local_ids = set(_ids_for_path(_client_path(book), "GMS")) if side != "tms" else set()
    tms_ids: set[str] = set()
    ms_ids: set[str] = set()
    if side != "local":
        tms_ids.update(_ids_for_path(_tms_img_path(book), "BMS"))
        cached_ms = _extracted_ms_path(book)
        if cached_ms is None and book in ms_skill_index():
            extracted = extract_ms_skill(book)
            cached_ms = extracted[0] if extracted is not None else None
        if cached_ms is not None:
            ms_ids.update(_ids_for_path(cached_ms, "BMS"))
            tms_ids.update(ms_ids)
    if side == "local":
        skill_ids = local_ids
    elif side == "tms":
        skill_ids = tms_ids
        names = dict(tms_names)
        names.update({key: value for key, value in local_names.items() if key not in names and value})
    else:
        skill_ids = local_ids | tms_ids
    items = []
    for skill_id in sorted(skill_ids, key=_natural_key):
        local = skill_id in local_ids
        tms = skill_id in tms_ids
        status = "both" if local and tms else "local" if local else "missing"
        if availability not in ("all", status):
            continue
        name = names.get(skill_id, "")
        haystack = f"{skill_id} {name}".lower()
        if query and query not in haystack:
            continue
        items.append({
            "id": skill_id, "name": name or f"技能 {skill_id}", "status": status,
            "local": local, "tms": tms, "ms": skill_id in ms_ids,
            "iconSource": "local" if local and side != "tms" else ("ms" if skill_id in ms_ids else "tms"),
        })
    sources = _source_paths(book)
    return _ok(
        book=book, name=_job_name(book, book_names), group=_job_group(book),
        items=items, total=len(items), sources=sources, msError=None, side=side,
    )


@app.get("/api/skill/<book>/<skill_id>")
def detail(book: str, skill_id: str):
    book = _book(book)
    skill_id = _skill_id(skill_id)
    requested = str(request.args.get("source") or "local")
    local = _detail(book, skill_id, "local")
    tms_source = _preferred_tms_source(book)
    tms = _detail(book, skill_id, tms_source) if tms_source else None
    if requested == "local" and local is None:
        requested = tms_source or "ms"
    selected = local if requested == "local" and local else tms or local
    if selected is None:
        raise KeyError(f"技能不存在: {skill_id}")
    sources = _source_paths(book)
    extra = {
        "tms": _detail(book, skill_id, "tms") if sources["tms"]["exists"] and tms_source != "tms" else (tms if tms_source == "tms" else None),
        "ms": tms if tms_source == "ms" else (_detail(book, skill_id, "ms") if sources["ms"]["exists"] else None),
        "canvas": None,
    }
    if requested == "canvas":
        extra["canvas"] = _detail(book, skill_id, "canvas") if sources["canvas"]["exists"] else None
    preview_source = requested if requested in ("local", "tms", "ms", "canvas") else ("local" if local else tms_source)
    preview_detail = local if preview_source == "local" else extra.get(preview_source) or tms
    tracks = []
    want_preview = str(request.args.get("preview") or "") in ("1", "true", "yes")
    if want_preview and preview_detail is not None:
        path, region = _source_file(book, preview_source or "local")
        tracks = _preview_tracks(_skill_node(_load_image(path, region), skill_id))
        for track in tracks:
            for frame in track["frames"]:
                frame["url"] = (
                    f"/api/skill/{quote(book)}/{quote(skill_id)}/canvas"
                    f"?source={quote(preview_source or 'local')}&path={quote(frame['path'])}"
                )
    names, _books = _merged_strings()
    level_source = "local" if local else (preview_source or tms_source or "ms")
    if local:
        max_level = _max_level(_skill_node(_load_image(*_source_file(book, "local")), skill_id))
    else:
        level_path, level_region = _source_file(book, level_source)
        max_level = _max_level(_skill_node(_load_image(level_path, level_region), skill_id))
    return _ok(
        skill={"id": skill_id, "book": book, "name": names.get(skill_id, selected.get("name", ""))},
        local=local, tms=tms, tmsSource=tms_source, sources=sources,
        ms=extra["ms"], canvas=extra["canvas"], tmsImg=extra["tms"],
        diff=_diff(local["nodes"] if local else [], tms["nodes"] if tms else []),
        preview={"source": preview_source, "tracks": tracks},
        maxLevel=max_level,
    )


@app.get("/api/skill/<book>/<skill_id>/icon")
def icon(book: str, skill_id: str):
    book = _book(book)
    skill_id = _skill_id(skill_id)
    requested = str(request.args.get("source") or "")
    order = [requested] if requested in ("local", "ms", "tms", "canvas") else []
    for key in ("local", "ms", "tms"):
        if key not in order:
            order.append(key)
    for source in order:
        try:
            path, region = _source_file(book, source)
            image = _load_image(path, region)
            node = _skill_node(image, skill_id)
            canvas = node.child("icon") or node.child("iconDisabled") or node.child("iconMouseOver")
            if canvas is None:
                continue
            pixels = _decode_node_canvas(canvas, image, path, region)
            if pixels.size == (1, 1) and pixels.getbbox() is None:
                continue
            output = io.BytesIO()
            pixels.save(output, format="PNG")
            output.seek(0)
            return send_file(output, mimetype="image/png", max_age=3600)
        except (FileNotFoundError, KeyError, ValueError):
            continue
    return "", 404


@app.get("/api/skill/<book>/<skill_id>/canvas")
def canvas(book: str, skill_id: str):
    book = _book(book)
    skill_id = _skill_id(skill_id)
    source = str(request.args.get("source") or "local")
    rel = str(request.args.get("path") or "").strip("/")
    if not rel:
        raise ValueError("缺少 Canvas 路径")
    path, region = _source_file(book, source)
    image = _load_image(path, region)
    node = _skill_node(image, skill_id).get(rel)
    if node is None and source in ("ms", "tms") and _tms_canvas_path(book).is_file():
        canvas_path, canvas_region = _source_file(book, "canvas")
        canvas_image = _load_image(canvas_path, canvas_region)
        node = _skill_node(canvas_image, skill_id).get(rel)
        path, region, image = canvas_path, canvas_region, canvas_image
    if node is None:
        raise KeyError(rel)
    pixels = _decode_node_canvas(node, image, path, region)
    output = io.BytesIO()
    pixels.save(output, format="PNG")
    output.seek(0)
    return send_file(output, mimetype="image/png", max_age=3600)


@app.post("/api/skill/node")
def mutate_node():
    body = request.get_json(silent=True) or {}
    book = _book(body.get("book") or body.get("job"))
    skill_id = _skill_id(body.get("id"))
    operation = str(body.get("operation") or "")
    relative = tuple(part for part in str(body.get("path") or "").split("/") if part)
    with _WRITE_LOCK:
        if operation == "copyFromTms":
            source_book = _book(body.get("sourceBook") or book)
            source_id = _skill_id(body.get("sourceId") or skill_id)
            source = str(body.get("source") or _preferred_tms_source(source_book) or "")
            recursive = bool(body.get("recursive", True))
            raw_paths = body.get("paths")
            if isinstance(raw_paths, list) and raw_paths:
                relatives = _selected_relatives([str(path) for path in raw_paths])
            else:
                relatives = [relative]
            tms_path, region = _source_file(source_book, source)
            local_root = _skill_node(_load_image(_client_path(book), "GMS"), skill_id)
            tms_root = _skill_node(_load_image(tms_path, region), source_id)
            operations = _plan_copy_from_tms(local_root, tms_root, relatives, recursive)
            return _ok(
                item=_write_skill_ops(book, skill_id, operations),
                copied=len(operations),
                sourceBook=source_book,
                sourceId=source_id,
            )
        item = _write_skill_ops(book, skill_id, [{
            "operation": operation,
            "path": "/".join(relative),
            "name": body.get("name"),
            "kind": body.get("kind"),
            "values": body.get("values") or {},
        }])
    return _ok(item=item)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8794, debug=False)
