#!/usr/bin/env python3
"""Build a read-only Limbo hard-mode migration admission report.

The audit extracts modern control metadata from TMS Snowcrypt packs into a
temporary directory, resolves every Canvas outlink against the split IMG tree,
and writes a self-contained HTML report. It never writes client or server data.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzKey,
    WzRawDataProperty,
    WzStringProperty,
    WzSubProperty,
)
from wzpy.properties import WzVideoProperty  # noqa: E402


TMS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS")
DEFAULT_IMG_ROOT = TMS_ROOT / "MapleStory-IMG" / "Data"
DEFAULT_PACK_ROOT = TMS_ROOT / "MapleStory" / "Data" / "Packs"
DEFAULT_MS_PROBE = (
    TMS_ROOT
    / "black_mage_report_tools"
    / "ms_probe"
    / "bin"
    / "Debug"
    / "net8.0"
    / "MSProbe.dll"
)
DEFAULT_OUTPUT = ROOT / "output" / "limbo-migration-audit"
KEY = WzKey.for_region("BMS")

MAPS = [
    ("P1", 410011100, 380),
    ("P2-C", 410011300, 381),
    ("中场", 410011400, 385),
    ("P2-D", 410011500, 382),
    ("P3", 410011700, 383),
]

SOURCE_MOBS_BY_STAGE = {
    "P1": [8881300, 8881302],
    "P2-C": [8881308, 8881309, 8881310, 8881311, 8881312, 8881313, 8881314],
    "P2-D": [8881315],
    "P3": [8881320, 8881324, 8881325, 8881329, 8881333, 8881334, 8881338,
           8881339, 8881340, 8881341, 8881342],
}

HARD_MOB_LABELS = {
    8881350: "幽灵 A", 8881351: "P1 控制体 1011", 8881352: "幽灵 B",
    8881353: "P1 控制体 1013", 8881357: "P1 控制体 1014",
    8881358: "幽灵 C 的心脏", 8881359: "C 普通右", 8881360: "C 普通左",
    8881361: "C 强化右", 8881362: "C 强化左", 8881363: "幽灵 C",
    8881364: "暴走的幽灵 C", 8881365: "幽灵 D", 8881366: "P2-D 控制体 1020",
    8881367: "P2-D 控制体 1022", 8881370: "林波黑形态",
    8881371: "P3 控制体 1024", 8881372: "P3 控制体 1026",
    8881373: "P3 控制体 1025", 8881374: "黑形态攻击实体",
    8881375: "林波白形态", 8881376: "P3 控制体 1030",
    8881377: "P3 控制体 1031", 8881378: "P3 控制体 1032",
    8881379: "白形态攻击实体", 8881382: "领悟真理的林波",
    8881383: "背后的贪吃鬼", 8881384: "矛盾的真理",
    8881385: "实验体 CD / HP 同步体", 8881388: "根源之影",
    8881389: "捕食者", 8881390: "白形态", 8881391: "消化酶",
    8881392: "捕食者", 8881393: "P3 控制体 1028",
    8881394: "P3 控制体 1034", 8881395: "P3 控制体 1035",
    8881396: "P3 控制体 1036",
}

OUTLINK_IMAGE = re.compile(r"^(.*?\.img)/(.*)$")
MOB_CANVAS_ID = re.compile(r"^Mob/_Canvas/(\d+)\.img/")


def scalar(node, name: str, default=None):
    child = node.child(name) if node is not None and hasattr(node, "child") else None
    if child is None:
        return default
    if hasattr(child, "x") and hasattr(child, "y"):
        return [int(child.x), int(child.y)]
    return getattr(child, "value", default)


def sort_key(node):
    return (0, int(node.name)) if node.name.isdigit() else (1, node.name)


def walk(node, prefix=""):
    for child in node.children() if hasattr(node, "children") else []:
        path = f"{prefix}/{child.name}" if prefix else child.name
        yield path, child
        yield from walk(child, path)


def descendants(node):
    return sum(1 for _ in walk(node))


class ImageCache:
    def __init__(self, img_root: Path):
        self.img_root = img_root
        self.images: dict[str, WzImage] = {}

    def load(self, relative: str) -> WzImage:
        if relative not in self.images:
            path = self.img_root / relative
            image = WzImage.from_file(str(path), key=KEY, name=path.name)
            image.parse()
            self.images[relative] = image
        return self.images[relative]

    def resolve_outlink(self, value: str):
        match = OUTLINK_IMAGE.match(value)
        if not match:
            return None, f"不支持的 outlink: {value}"
        image_path, property_path = match.groups()
        path = self.img_root / image_path
        if not path.is_file():
            return None, f"缺少 IMG: {image_path}"
        try:
            node = self.load(image_path).root.get(property_path)
        except Exception as exc:  # report malformed source without stopping other checks
            return None, f"解析失败 {value}: {exc}"
        if not isinstance(node, WzCanvasProperty):
            return None, f"目标不是 Canvas: {value}"
        return node, None


def load_standalone(path: Path) -> WzImage:
    image = WzImage.from_file(str(path), key=KEY, name=path.name)
    image.parse()
    return image


def run_probe(dotnet: str, probe: Path, pack: Path, output: Path, prefix: str):
    result = subprocess.run(
        [dotnet, str(probe), str(pack), str(output), prefix],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def extract_metadata(dotnet: str, probe: Path, packs: Path, output: Path):
    run_probe(dotnet, probe, packs / "Mob_00000.ms", output, "Mob/88813")
    run_probe(dotnet, probe, packs / "Mob_00002.ms", output, "Mob/BossPattern/BossLimbo.img")
    run_probe(dotnet, probe, packs / "Mob_00003.ms", output, "Mob/BossPattern/PatternSystem.img")


def canvas_format(canvas: WzCanvasProperty) -> int:
    return int(canvas.format + canvas.format2)


def canvas_summary(canvases: list[WzCanvasProperty]) -> dict:
    formats = Counter(canvas_format(canvas) for canvas in canvases)
    memory = sum(int(canvas.width) * int(canvas.height) * 4 for canvas in canvases)
    max_width = max((int(canvas.width) for canvas in canvases), default=0)
    max_height = max((int(canvas.height) for canvas in canvases), default=0)
    return {
        "canvases": len(canvases),
        "formats": {str(key): value for key, value in sorted(formats.items())},
        "rgbaMiB": round(memory / 1024 / 1024, 1),
        "maxWidth": max_width,
        "maxHeight": max_height,
        "over2048": sum(max(canvas.width, canvas.height) > 2048 for canvas in canvases),
        "over4096": sum(max(canvas.width, canvas.height) > 4096 for canvas in canvases),
        "over8192": sum(max(canvas.width, canvas.height) > 8192 for canvas in canvases),
    }


def direct_canvas_groups(root, prefix="") -> list[dict]:
    groups = []

    def visit(node, path):
        frames = sorted(
            [child for child in node.children() if isinstance(child, WzCanvasProperty)],
            key=sort_key,
        )
        if frames:
            groups.append({"path": path, **canvas_summary(frames)})
        for child in node.children():
            if isinstance(child, WzSubProperty) and not isinstance(child, WzCanvasProperty):
                visit(child, f"{path}/{child.name}" if path else child.name)

    visit(root, prefix)
    return groups


def actual_frame(cache: ImageCache, frame: WzCanvasProperty):
    link = scalar(frame, "_outlink")
    if not link:
        return frame, None, None
    resolved, error = cache.resolve_outlink(str(link))
    return resolved, str(link), error


def pattern_stage(category: int) -> str:
    if 1010 <= category <= 1014:
        return "P1"
    if 1015 <= category <= 1019:
        return "P2-C"
    if 1020 <= category <= 1022:
        return "P2-D"
    if 1023 <= category <= 1036:
        return "P3"
    return "未分类"


def inspect_hard_mobs(metadata_dir: Path, cache: ImageCache):
    rows = []
    broken = []
    category_mobs: dict[int, list[int]] = defaultdict(list)
    all_actions = []
    for path in sorted(metadata_dir.glob("Mob_88813*.img")):
        mob_id = int(path.stem.rsplit("_", 1)[1])
        if mob_id < 8881350:
            continue
        image = load_standalone(path)
        info = image.root.child("info")
        pattern = info.child("patternSys") if info else None
        category = int(scalar(pattern, "category", 0) or 0)
        if category:
            category_mobs[category].append(mob_id)
        references = set()
        actions = []
        for action in image.root.children():
            if action.name == "info" or not hasattr(action, "children"):
                continue
            frames = sorted(
                [child for child in action.children() if isinstance(child, WzCanvasProperty)],
                key=sort_key,
            )
            if not frames:
                continue
            actual = []
            delay = 0
            for frame in frames:
                delay += int(scalar(frame, "delay", 0) or 0)
                resolved, link, error = actual_frame(cache, frame)
                if link:
                    match = MOB_CANVAS_ID.match(link)
                    if match:
                        references.add(int(match.group(1)))
                if error:
                    broken.append({"owner": f"{mob_id}/{action.name}/{frame.name}", "error": error})
                elif resolved is not None:
                    actual.append(resolved)
            summary = canvas_summary(actual)
            action_row = {
                "mobId": mob_id,
                "action": action.name,
                "logicalFrames": len(frames),
                "durationMs": delay,
                **summary,
            }
            actions.append(action_row)
            all_actions.append(action_row)
        rows.append({
            "id": mob_id,
            "label": HARD_MOB_LABELS.get(mob_id, "困难控制/辅助体"),
            "category": category or None,
            "stage": pattern_stage(category) if category else "P3/辅助",
            "difficulty": scalar(pattern, "difficulty") if pattern else None,
            "canvasIds": sorted(references),
            "actions": actions,
            "controllerOnly": not references,
        })
    return rows, category_mobs, all_actions, broken


def collect_outlink_errors(image: WzImage, owner: str, cache: ImageCache):
    errors = []
    links = 0
    for path, node in walk(image.root):
        if node.name != "_outlink":
            continue
        links += 1
        _, error = cache.resolve_outlink(str(node.value))
        if error:
            errors.append({"owner": f"{owner}/{path}", "error": error})
    return links, errors


def relevant_leaf_values(node, wanted: set[str]) -> dict[str, list]:
    result: dict[str, list] = defaultdict(list)
    for path, child in walk(node):
        if child.name not in wanted:
            continue
        value = getattr(child, "value", None)
        if value is not None and value not in result[child.name]:
            result[child.name].append(value)
    return dict(result)


def inspect_patterns(pattern_system: WzImage, boss_limbo: WzImage, category_mobs):
    rows = []
    wanted = {
        "action", "chainPattern", "effectImgName", "animation", "cooltimeMS",
        "startCooltimeMS", "fixDamR", "attackDelay", "disease", "level",
    }
    for category in range(1010, 1037):
        metadata = pattern_system.root.child(str(category))
        visual = boss_limbo.root.child(str(category))
        visual_groups = direct_canvas_groups(visual, str(category)) if visual else []
        refs = relevant_leaf_values(metadata, wanted) if metadata else {}
        rows.append({
            "category": category,
            "stage": pattern_stage(category),
            "mobIds": sorted(category_mobs.get(category, [])),
            "metadata": metadata is not None,
            "metadataNodes": descendants(metadata) if metadata else 0,
            "visualBranch": visual is not None,
            "visualSequences": len(visual_groups),
            "visualFrames": sum(group["canvases"] for group in visual_groups),
            "actions": refs.get("action", []),
            "effectRefs": refs.get("effectImgName", []),
            "controlOnly": bool(metadata) and not visual_groups,
        })
    return rows


def atlas_pages(text: str):
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        if not line or line[:1].isspace() or not lines[index + 1].startswith("size:"):
            continue
        size = re.search(r"(\d+)\s*,\s*(\d+)", lines[index + 1])
        if size:
            yield line.strip(), int(size.group(1)), int(size.group(2))


def is_spine(node) -> bool:
    return node is not None and any(
        isinstance(child, WzRawDataProperty) for child in node.children()
    ) and bool(scalar(node, "spine"))


def inspect_maps(cache: ImageCache):
    back_root = cache.load("Map/Back/bossLimbo.img").root
    obj_root = cache.load("Map/Obj/bossLimbo.img").root
    source_groups = direct_canvas_groups(
        cache.load("Map/Back/_Canvas/bossLimbo.img").root, "back"
    ) + direct_canvas_groups(
        cache.load("Map/Obj/_Canvas/bossLimbo.img").root, "obj"
    )
    resource_nodes = {}
    map_rows = []
    for stage, map_id, expected_field_type in MAPS:
        root = cache.load(f"Map/Map/Map4/{map_id}.img").root
        info = root.child("info")
        resources = []
        back = root.child("back")
        for entry in back.children() if back else []:
            if scalar(entry, "bS") != "bossLimbo":
                continue
            key = f"back/spine/{scalar(entry, 'no')}"
            node = back_root.get(f"spine/{scalar(entry, 'no')}")
            if node:
                resource_nodes[key] = node
                resources.append(key)
        for layer in [child for child in root.children() if child.name.isdigit()]:
            obj = layer.child("obj")
            for entry in obj.children() if obj else []:
                if scalar(entry, "oS") != "bossLimbo":
                    continue
                branch = "/".join(str(scalar(entry, key, "")) for key in ("l0", "l1", "l2"))
                key = f"obj/{branch}"
                node = obj_root.get(branch)
                if node:
                    resource_nodes[key] = node
                    resources.append(key)
        map_rows.append({
            "stage": stage,
            "mapId": map_id,
            "fieldType": scalar(info, "fieldType"),
            "expectedFieldType": expected_field_type,
            "bgm": scalar(info, "bgm", ""),
            "resources": sorted(set(resources)),
        })

    spines = []
    for path, node in sorted(resource_nodes.items()):
        if is_spine(node):
            atlas = next(
                (child for child in node.children()
                 if isinstance(child, WzStringProperty) and child.name.endswith(".atlas")),
                None,
            )
            skeleton = next(
                (child for child in node.children() if isinstance(child, WzRawDataProperty)),
                None,
            )
            pages = []
            if atlas:
                for name, width, height in atlas_pages(str(atlas.value)):
                    page = node.child(name)
                    actual = None
                    error = None
                    if isinstance(page, WzCanvasProperty):
                        actual, _, error = actual_frame(cache, page)
                    found = isinstance(actual, WzCanvasProperty) and error is None
                    pages.append({
                        "name": name,
                        "width": width,
                        "height": height,
                        "found": found,
                        "actualWidth": int(actual.width) if found else None,
                        "actualHeight": int(actual.height) if found else None,
                    })
            spines.append({
                "path": path,
                "runtime": scalar(node, "spine"),
                "skeletonBytes": int(skeleton.value) if skeleton else 0,
                "pages": pages,
            })
    return map_rows, spines, source_groups, aggregate_family(source_groups)


def aggregate_family(groups: list[dict]) -> dict:
    formats = Counter()
    for group in groups:
        formats.update({int(key): value for key, value in group["formats"].items()})
    return {
        "canvases": sum(group["canvases"] for group in groups),
        "formats": {str(key): value for key, value in sorted(formats.items())},
        "rgbaMiB": round(sum(group["rgbaMiB"] for group in groups), 1),
        "maxWidth": max((group["maxWidth"] for group in groups), default=0),
        "maxHeight": max((group["maxHeight"] for group in groups), default=0),
        "over2048": sum(group["over2048"] for group in groups),
        "over4096": sum(group["over4096"] for group in groups),
        "over8192": sum(group["over8192"] for group in groups),
    }


def build_audit(args) -> dict:
    cache = ImageCache(args.img_root)
    with tempfile.TemporaryDirectory(prefix="limbo-ms-audit.") as temporary:
        metadata_dir = Path(temporary)
        extract_metadata(args.dotnet, args.ms_probe, args.pack_root, metadata_dir)
        hard_mobs, category_mobs, hard_actions, mob_errors = inspect_hard_mobs(metadata_dir, cache)
        boss_limbo = load_standalone(metadata_dir / "Mob_BossPattern_BossLimbo.img")
        pattern_system = load_standalone(metadata_dir / "Mob_BossPattern_PatternSystem.img")
        pattern_links, pattern_errors = collect_outlink_errors(
            boss_limbo, "Mob/BossPattern/BossLimbo.img", cache
        )
        patterns = inspect_patterns(pattern_system, boss_limbo, category_mobs)

    mob_groups = []
    visual_images = []
    for stage, ids in SOURCE_MOBS_BY_STAGE.items():
        for mob_id in ids:
            image = cache.load(f"Mob/_Canvas/{mob_id}.img")
            visual_images.append(image)
            mob_groups.extend(direct_canvas_groups(image.root, f"{stage}/{mob_id}"))
    pattern_source = cache.load("Mob/BossPattern/_Canvas/BossLimbo.img")
    visual_images.append(pattern_source)
    pattern_groups = direct_canvas_groups(pattern_source.root)
    maps, spines, map_groups, map_stats = inspect_maps(cache)
    visual_images.extend([
        cache.load("Map/Back/_Canvas/bossLimbo.img"),
        cache.load("Map/Obj/_Canvas/bossLimbo.img"),
    ])
    native_video_count = sum(
        isinstance(node, WzVideoProperty)
        for image in visual_images for _, node in walk(image.root)
    )

    mob_stats = aggregate_family(mob_groups)
    pattern_stats = aggregate_family(pattern_groups)
    map_group_stats = aggregate_family(map_groups)
    combined_groups = mob_groups + pattern_groups + map_groups
    combined_stats = aggregate_family(combined_groups)

    missing_spine_pages = [
        {"spine": spine["path"], **page}
        for spine in spines for page in spine["pages"] if not page["found"]
    ]
    oversized_spine_pages = [
        {"spine": spine["path"], **page}
        for spine in spines for page in spine["pages"]
        if max(page["width"], page["height"]) > 4096
    ]
    unresolved = mob_errors + pattern_errors
    missing_pattern_metadata = [row["category"] for row in patterns if not row["metadata"]]
    missing_pattern_visual = [
        row["category"] for row in patterns
        if not row["visualBranch"] or (not row["visualFrames"] and not row["controlOnly"])
    ]

    high_memory_actions = sorted(
        [row for row in hard_actions if row["rgbaMiB"] >= 80],
        key=lambda row: row["rgbaMiB"],
        reverse=True,
    )
    high_memory_patterns = sorted(
        [row for row in pattern_groups if row["rgbaMiB"] >= 80 or row["over2048"]],
        key=lambda row: (row["rgbaMiB"], row["over2048"]),
        reverse=True,
    )

    gates = [
        {
            "name": "困难控制元数据",
            "status": "pass" if not missing_pattern_metadata else "blocked",
            "detail": "Mob_00000.ms 与 Mob_00003.ms 已提取困难 Mob、PatternSystem 和阶段地图配置。",
        },
        {
            "name": "技能视觉引用闭合",
            "status": "pass" if not unresolved and not missing_pattern_visual else "blocked",
            "detail": f"已验证 {pattern_links} 条 BossPattern outlink；未解析引用 {len(unresolved)} 条。",
        },
        {
            "name": "DXT5 写入兼容",
            "status": "blocked" if int(combined_stats["formats"].get("2050", 0)) else "pass",
            "detail": "当前 wzpy 能解码 DXT5，但写入器明确拒绝 DXT；必须实现编码或转为旧格式。",
        },
        {
            "name": "纹理与动作内存",
            "status": "blocked" if combined_stats["over2048"] or high_memory_actions else "pass",
            "detail": f"超过 2048 的 Canvas {combined_stats['over2048']} 张；80MiB 以上困难动作 {len(high_memory_actions)} 个。",
        },
        {
            "name": "Spine 场景完整性",
            "status": "blocked" if missing_spine_pages or oversized_spine_pages else "pass",
            "detail": f"缺页 {len(missing_spine_pages)}；atlas 边长超过 4096 的页 {len(oversized_spine_pages)}。",
        },
        {
            "name": "MCV 并发与实机能力",
            "status": "blocked",
            "detail": "当前全局单 Player；新播放会 Stop 当前视频，且未记录目标设备 D3D8 MaxTexture caps。",
        },
    ]

    return {
        "title": "林波困难模式迁移准入审计",
        "verdict": "BLOCKED" if any(gate["status"] == "blocked" for gate in gates) else "PASS",
        "source": {
            "imgRoot": str(args.img_root),
            "packRoot": str(args.pack_root),
            "metadata": ["Mob_00000.ms", "Mob_00002.ms", "Mob_00003.ms"],
        },
        "gates": gates,
        "maps": maps,
        "hardMobs": hard_mobs,
        "patterns": patterns,
        "links": {
            "bossPatternOutlinks": pattern_links,
            "unresolved": unresolved,
        },
        "resources": {
            "bossPattern": pattern_stats,
            "mobs": mob_stats,
            "mapFrameGroups": map_group_stats,
            "mapAllCanvas": map_stats,
            "combined": combined_stats,
            "nativeVideoCount": native_video_count,
            "spines": spines,
            "missingSpinePages": missing_spine_pages,
            "oversizedSpinePages": oversized_spine_pages,
            "highMemoryActions": high_memory_actions,
            "highMemoryPatterns": high_memory_patterns,
        },
        "mcv": {
            "currentModel": "进程内唯一 Player；BDV_PlayFile() 先 Stop()，同一时刻只播放一个 MCV。",
            "conflict": "林波转场或全屏机制会中断正在播放的五/六转技能，反向亦然。",
            "recommendation": "采用两个固定通道：boss-scene 与 player-skill；每通道由独立 Player 支撑，同通道按优先级替换。不要开放无上限多实例。",
            "simpleFallback": "在多通道完成前，只允许不可操作的阶段转场使用 MCV；战斗中可重叠的大技能保留为裁剪/分块 Canvas。",
        },
        "admissionWork": [
            "补回缺失 Spine atlas 页，并将所有 Spine 4.1 场景预渲染为旧客户端可用资源。",
            "确定统一纹理策略：DXT5 编码，或批量转 format 1/2；每个动作控制在 80-100MiB 内。",
            "把超过设备上限的画面裁剪、分块或缩放；不得把 8192 容器上限当成 D3D8 实机上限。",
            "实现 boss-scene / player-skill 两个固定 MCV 通道，或限制林波仅在不可操作转场播放 MCV。",
            "在目标 Windows/Winlator 设备记录 MaxTextureWidth、MaxTextureHeight、MaxTextureAspectRatio，并实测 2048/4096 纹理创建。",
            "用 1 个 DXT5 Mob、1 个 2812px BossPattern、1 个预渲染 Spine 背景、1 个林波转场 MCV 做最小样机。",
        ],
    }


def fmt(value):
    return html.escape(str(value))


def render_html(audit: dict) -> str:
    payload = json.dumps(audit, ensure_ascii=False).replace("</", "<\\/")
    verdict_class = "blocked" if audit["verdict"] == "BLOCKED" else "pass"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{fmt(audit['title'])}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#111315; --panel:#191c1f; --line:#33383d; --text:#eef0f2; --muted:#a9b0b6; --pass:#3fc27f; --warn:#e6ae45; --bad:#ee6a66; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
    header {{ border-bottom:1px solid var(--line); background:#15181a; }} .wrap {{ width:min(1440px,calc(100% - 32px)); margin:auto; }}
    header .wrap {{ padding:28px 0 24px; display:flex; align-items:flex-end; justify-content:space-between; gap:24px; }}
    h1 {{ font-size:28px; margin:0 0 6px; letter-spacing:0; }} h2 {{ font-size:19px; margin:0 0 14px; }} p {{ margin:0; color:var(--muted); }}
    .verdict {{ padding:8px 12px; border:1px solid var(--bad); color:var(--bad); font-weight:700; }} .verdict.pass {{ border-color:var(--pass); color:var(--pass); }}
    main {{ padding:24px 0 48px; }} section {{ padding:22px 0; border-bottom:1px solid var(--line); }}
    .gates {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; }}
    .gate {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--bad); padding:14px; border-radius:4px; }} .gate.pass {{ border-left-color:var(--pass); }}
    .gate strong {{ display:block; margin-bottom:6px; }} .status {{ float:right; color:var(--bad); }} .pass .status {{ color:var(--pass); }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }} .stat {{ background:var(--panel); border:1px solid var(--line); padding:14px; border-radius:4px; }}
    .stat b {{ display:block; font-size:22px; }} .stat span {{ color:var(--muted); }}
    .table-wrap {{ overflow:auto; border:1px solid var(--line); }} table {{ width:100%; border-collapse:collapse; min-width:800px; }} th,td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ position:sticky; top:0; background:#202428; color:#cdd2d6; }} tr:last-child td {{ border-bottom:0; }}
    code {{ color:#d7e4ed; }} .bad {{ color:var(--bad); }} .ok {{ color:var(--pass); }} .muted {{ color:var(--muted); }}
    .note {{ border-left:3px solid var(--warn); background:#1c1b17; padding:12px 14px; margin:12px 0; color:#d8d1c2; }}
    ol {{ margin:0; padding-left:22px; }} li+li {{ margin-top:7px; }} details {{ border:1px solid var(--line); margin-top:10px; }} summary {{ cursor:pointer; padding:10px 12px; background:var(--panel); }} details .inside {{ padding:12px; }}
    @media (max-width:640px) {{ header .wrap {{ align-items:flex-start; flex-direction:column; }} .wrap {{ width:min(100% - 20px,1440px); }} h1 {{ font-size:23px; }} }}
  </style>
</head>
<body>
<header><div class="wrap"><div><h1>{fmt(audit['title'])}</h1><p>直接证据：TMS v280 IMG + Snowcrypt MS 控制包；报告为只读预检，不代表已迁移。</p></div><div class="verdict {verdict_class}">{fmt(audit['verdict'])}</div></div></header>
<main class="wrap">
  <section><h2>准入门</h2><div id="gates" class="gates"></div></section>
  <section><h2>资源总量</h2><div id="stats" class="stats"></div><div class="note">format 2050 是 DXT5。当前读取器可解码，但写入器不能编码，因此“资源存在”不等于“现有迁移流水线可直接写入”。</div></section>
  <section><h2>困难 Mob 正式映射</h2><p>困难根 IMG 的 `_outlink` 直接证明复用关系；控制体没有独立 Canvas 属正常结构。</p><div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>ID</th><th>阶段</th><th>Pattern</th><th>复用 Canvas</th><th>动作</th><th>最大动作内存</th></tr></thead><tbody id="mobs"></tbody></table></div></section>
  <section><h2>Pattern 完整性</h2><p>阶段范围来自困难 Mob 的 `patternSys/category`，修正了旧预览的编号猜测。</p><div class="table-wrap" style="margin-top:12px"><table><thead><tr><th>类别</th><th>阶段</th><th>困难 Mob</th><th>控制节点</th><th>视觉序列/帧</th><th>动作</th></tr></thead><tbody id="patterns"></tbody></table></div></section>
  <section><h2>已确认风险</h2><div id="risks"></div></section>
  <section><h2>MCV 冲突结论</h2><div class="note" id="mcv"></div></section>
  <section><h2>开始迁移前必须完成</h2><ol id="work"></ol></section>
  <section><details><summary>查看原始审计 JSON</summary><div class="inside"><pre id="raw" style="white-space:pre-wrap;word-break:break-word"></pre></div></details></section>
</main>
<script id="audit" type="application/json">{payload}</script>
<script>
const d=JSON.parse(document.getElementById('audit').textContent);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
document.getElementById('gates').innerHTML=d.gates.map(g=>`<div class="gate ${{g.status}}"><strong>${{esc(g.name)}}<span class="status">${{g.status==='pass'?'通过':'阻塞'}}</span></strong><p>${{esc(g.detail)}}</p></div>`).join('');
const s=d.resources.combined;
document.getElementById('stats').innerHTML=[['Canvas',s.canvases],['原生视频',d.resources.nativeVideoCount],['DXT5',s.formats['2050']||0],['> 2048',s.over2048],['> 4096',s.over4096],['RGBA8 总解码量',s.rgbaMiB+' MiB'],['未解析 outlink',d.links.unresolved.length]].map(x=>`<div class="stat"><b>${{esc(x[1])}}</b><span>${{esc(x[0])}}</span></div>`).join('');
document.getElementById('mobs').innerHTML=d.hardMobs.filter(m=>m.category||m.canvasIds.length).map(m=>{{const peak=m.actions.reduce((a,x)=>x.rgbaMiB>a.rgbaMiB?x:a,{{rgbaMiB:0,action:'-'}});return `<tr><td><code>${{m.id}}</code><br><span class="muted">${{esc(m.label)}}</span></td><td>${{esc(m.stage)}}</td><td>${{m.category||'-'}}</td><td>${{m.canvasIds.join(', ')||'控制体'}}</td><td>${{m.actions.length}}</td><td class="${{peak.rgbaMiB>=80?'bad':''}}">${{esc(peak.action)}} · ${{peak.rgbaMiB}} MiB</td></tr>`}}).join('');
document.getElementById('patterns').innerHTML=d.patterns.map(p=>`<tr><td>${{p.category}}</td><td>${{esc(p.stage)}}</td><td>${{p.mobIds.join(', ')||'-'}}</td><td class="${{p.metadata?'ok':'bad'}}">${{p.metadata?p.metadataNodes:'缺失'}}</td><td class="${{p.visualBranch?'':'bad'}}">${{p.controlOnly?'控制类':p.visualSequences+' / '+p.visualFrames}}</td><td>${{esc(p.actions.join(', ')||'-')}}</td></tr>`).join('');
const miss=d.resources.missingSpinePages, over=d.resources.oversizedSpinePages, actions=d.resources.highMemoryActions, patterns=d.resources.highMemoryPatterns;
document.getElementById('risks').innerHTML=`<div class="table-wrap"><table><thead><tr><th>风险</th><th>数量</th><th>具体证据</th></tr></thead><tbody>
<tr><td>Spine 缺页</td><td>${{miss.length}}</td><td>${{miss.map(x=>esc(x.spine+'/'+x.name+' '+x.width+'x'+x.height)).join('<br>')||'无'}}</td></tr>
<tr><td>Spine >4096</td><td>${{over.length}}</td><td>${{over.map(x=>esc(x.spine+'/'+x.name+' '+x.width+'x'+x.height)).join('<br>')||'无'}}</td></tr>
<tr><td>困难动作 >=80MiB</td><td>${{actions.length}}</td><td>${{actions.slice(0,12).map(x=>esc(x.mobId+'/'+x.action+' '+x.rgbaMiB+'MiB '+x.maxWidth+'x'+x.maxHeight)).join('<br>')||'无'}}</td></tr>
<tr><td>BossPattern 大序列</td><td>${{patterns.length}}</td><td>${{patterns.slice(0,12).map(x=>esc(x.path+' '+x.rgbaMiB+'MiB '+x.maxWidth+'x'+x.maxHeight)).join('<br>')||'无'}}</td></tr>
</tbody></table></div>`;
document.getElementById('mcv').innerHTML=`<strong>${{esc(d.mcv.currentModel)}}</strong><br>${{esc(d.mcv.conflict)}}<br><br>${{esc(d.mcv.recommendation)}}<br>${{esc(d.mcv.simpleFallback)}}`;
document.getElementById('work').innerHTML=d.admissionWork.map(x=>`<li>${{esc(x)}}</li>`).join('');
document.getElementById('raw').textContent=JSON.stringify(d,null,2);
</script>
</body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--img-root", type=Path, default=DEFAULT_IMG_ROOT)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    parser.add_argument("--ms-probe", type=Path, default=DEFAULT_MS_PROBE)
    parser.add_argument("--dotnet", default=shutil.which("dotnet") or "/opt/homebrew/bin/dotnet")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for required in (args.img_root, args.pack_root, args.ms_probe):
        if not required.exists():
            raise SystemExit(f"missing required source: {required}")
    audit = build_audit(args)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "index.html").write_text(render_html(audit), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "verdict": audit["verdict"],
        "gates": audit["gates"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
