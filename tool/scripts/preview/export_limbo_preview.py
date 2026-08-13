#!/usr/bin/env python3
"""Export a read-only, browser-playable Limbo resource preview from TMS IMG files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image


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
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas  # noqa: E402


DEFAULT_TMS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
DEFAULT_OUTPUT = ROOT / "output" / "limbo-resource-preview"
KEY = WzKey.for_region("BMS")

STAGES = [
    {"id": "p1", "label": "P1 · 光谱体", "mapId": "410011100", "fieldType": 380},
    {"id": "p2c", "label": "P2-C · 空间 C", "mapId": "410011300", "fieldType": 381},
    {"id": "middle", "label": "中场 · 通道", "mapId": "410011400", "fieldType": 385},
    {"id": "p2d", "label": "P2-D · 空间 D", "mapId": "410011500", "fieldType": 382},
    {"id": "p3", "label": "P3 · 黑白形态", "mapId": "410011700", "fieldType": 383},
]

MOBS_BY_STAGE = {
    "p1": ["8881300", "8881302"],
    "p2c": ["8881308", "8881309", "8881310", "8881311", "8881312", "8881313", "8881314"],
    "middle": [],
    "p2d": ["8881315"],
    "p3": ["8881320", "8881324", "8881325", "8881329", "8881333", "8881334", "8881338", "8881339", "8881340", "8881341", "8881342"],
}

MOB_LABELS = {
    "8881300": "P1 光谱体 A",
    "8881302": "P1 光谱体 B",
    "8881308": "P2-C 林波主体",
    "8881309": "P2-C 技能实体 1",
    "8881310": "P2-C 技能实体 2",
    "8881311": "P2-C 技能实体 3",
    "8881312": "P2-C 技能实体 4",
    "8881313": "P2-C 花形辅助",
    "8881314": "P2-C 变形辅助",
    "8881315": "P2-D 人形主体",
    "8881320": "P3 黑形态",
    "8881324": "P3 黑形态攻击实体",
    "8881325": "P3 白形态",
    "8881329": "P3 白形态攻击实体",
    "8881333": "P3 辅助实体 1",
    "8881334": "P3 辅助实体 2",
    "8881338": "P3 辅助实体 3",
    "8881339": "P3 辅助实体 4",
    "8881340": "P3 辅助实体 5",
    "8881341": "P3 辅助实体 6",
    "8881342": "P3 辅助实体 7",
}


def scalar(node, name: str, default=None):
    child = node.child(name) if node else None
    return child.value if child is not None else default


def slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "asset"
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{clean}-{digest}"


def sort_key(node):
    return (0, int(node.name)) if node.name.isdigit() else (1, node.name)


class Exporter:
    def __init__(self, source: Path, output: Path, quick: bool):
        self.source = source
        self.output = output
        self.quick = quick
        self.images: dict[str, WzImage] = {}
        self.spines: dict[str, dict] = {}
        self.object_sequences: dict[str, dict] = {}

    def load(self, relative: str) -> WzImage:
        if relative not in self.images:
            path = self.source / relative
            self.images[relative] = WzImage.from_file(str(path), key=KEY, name=path.name)
        return self.images[relative]

    def resolve_canvas(self, canvas: WzCanvasProperty) -> WzCanvasProperty:
        outlink = scalar(canvas, "_outlink")
        if not outlink:
            return canvas
        marker = ".img/"
        if marker not in outlink:
            raise ValueError(f"unsupported canvas outlink: {outlink}")
        image_path, property_path = outlink.split(marker, 1)
        target = self.load(f"{image_path}.img").root.get(property_path)
        if not isinstance(target, WzCanvasProperty):
            raise ValueError(f"outlink does not resolve to Canvas: {outlink}")
        return target

    def save_canvas(self, canvas: WzCanvasProperty, target: Path, max_edge: int | None = None):
        if target.exists():
            return
        actual = self.resolve_canvas(canvas)
        image = decode_canvas(actual, region="BMS").convert("RGBA")
        if max_edge and max(image.size) > max_edge:
            scale = max_edge / max(image.size)
            image = image.resize(
                (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
                Image.Resampling.LANCZOS,
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix.lower() == ".png":
            image.save(target, compress_level=3)
        else:
            image.save(target, "WEBP", quality=82, method=4, alpha_quality=92)

    def export_sequence(self, node, category: str, logical_path: str, max_edge: int) -> dict | None:
        frames = sorted(
            [child for child in node.children() if isinstance(child, WzCanvasProperty)],
            key=sort_key,
        )
        if not frames:
            return None
        if self.quick:
            frames = frames[: min(8, len(frames))]

        folder = self.output / "assets" / category / slug(logical_path)
        result_frames = []
        left = top = 10**9
        right = bottom = -10**9
        for index, frame in enumerate(frames):
            origin = scalar(frame, "origin", (0, 0))
            if not isinstance(origin, tuple):
                origin = (0, 0)
            source_width, source_height = int(frame.width), int(frame.height)
            scale = min(1.0, max_edge / max(source_width, source_height))
            width = max(1, round(source_width * scale))
            height = max(1, round(source_height * scale))
            origin_x = round(int(origin[0]) * scale)
            origin_y = round(int(origin[1]) * scale)
            filename = f"{index:04d}.webp"
            self.save_canvas(frame, folder / filename, max_edge=max_edge)
            frame_left, frame_top = -origin_x, -origin_y
            left, top = min(left, frame_left), min(top, frame_top)
            right = max(right, frame_left + width)
            bottom = max(bottom, frame_top + height)
            result_frames.append(
                {
                    "src": str((folder / filename).relative_to(self.output)),
                    "width": width,
                    "height": height,
                    "origin": [origin_x, origin_y],
                    "delay": max(16, int(scalar(frame, "delay", 100) or 100)),
                }
            )
        return {
            "path": logical_path,
            "frameCount": len(result_frames),
            "sourceFrameCount": len([c for c in node.children() if isinstance(c, WzCanvasProperty)]),
            "bounds": [left, top, right, bottom],
            "frames": result_frames,
        }

    def spine_node(self, node) -> bool:
        return any(isinstance(child, WzRawDataProperty) for child in node.children()) and bool(
            scalar(node, "spine")
        )

    @staticmethod
    def atlas_pages(atlas_text: str) -> list[tuple[str, int, int]]:
        lines = atlas_text.splitlines()
        pages = []
        for index, line in enumerate(lines[:-1]):
            if not line or line[:1].isspace() or not lines[index + 1].startswith("size:"):
                continue
            size = re.search(r"(\d+)\s*,\s*(\d+)", lines[index + 1])
            if size:
                pages.append((line.strip(), int(size.group(1)), int(size.group(2))))
        return pages

    def export_spine(self, logical_path: str, node) -> dict:
        if logical_path in self.spines:
            return self.spines[logical_path]
        folder = self.output / "assets" / "spine" / slug(logical_path)
        folder.mkdir(parents=True, exist_ok=True)
        atlas = next(
            child for child in node.children() if isinstance(child, WzStringProperty) and child.name.endswith(".atlas")
        )
        skeleton = next(child for child in node.children() if isinstance(child, WzRawDataProperty))
        (folder / atlas.name).write_text(atlas.value.lstrip("\n"), encoding="utf-8")
        (folder / skeleton.name).write_bytes(skeleton.data())
        pages = []
        missing_pages = []
        for page_name, width, height in self.atlas_pages(atlas.value):
            page = node.child(page_name)
            target = folder / page_name
            if isinstance(page, WzCanvasProperty):
                self.save_canvas(page, target)
            else:
                if not target.exists():
                    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(target, compress_level=1)
                missing_pages.append({"name": page_name, "width": width, "height": height})
            pages.append(page_name)
        resource = {
            "path": logical_path,
            "name": scalar(node, "spine"),
            "atlas": str((folder / atlas.name).relative_to(self.output)),
            "skel": str((folder / skeleton.name).relative_to(self.output)),
            "pages": pages,
            "missingPages": missing_pages,
            "bytes": int(skeleton.value),
        }
        self.spines[logical_path] = resource
        return resource

    def export_map_resource(self, logical_path: str, node) -> dict | None:
        if self.spine_node(node):
            return {"type": "spine", "resource": self.export_spine(logical_path, node)}
        sequence = self.export_sequence(node, "objects", logical_path, max_edge=1600)
        if sequence:
            self.object_sequences[logical_path] = sequence
            return {"type": "frames", "resource": sequence}
        return None

    def export_maps(self) -> list[dict]:
        back_root = self.load("Map/Back/bossLimbo.img").root
        obj_root = self.load("Map/Obj/bossLimbo.img").root
        exported = []
        for stage in STAGES:
            map_id = stage["mapId"]
            root = self.load(f"Map/Map/Map4/{map_id}.img").root
            info = root.child("info")
            vr = [int(scalar(info, name, fallback)) for name, fallback in zip(
                ["VRLeft", "VRTop", "VRRight", "VRBottom"], [-683, -384, 683, 384]
            )]
            layers = []
            back = root.child("back")
            if back:
                for entry in back.children():
                    if scalar(entry, "bS") != "bossLimbo":
                        continue
                    path = f"back/spine/{scalar(entry, 'no')}"
                    resource_node = back_root.get(f"spine/{scalar(entry, 'no')}")
                    resource = self.export_map_resource(path, resource_node) if resource_node else None
                    if resource:
                        layers.append(self.layer_manifest("back", entry, resource, -100 + int(entry.name or 0)))
            for map_layer in [child for child in root.children() if child.name.isdigit()]:
                obj = map_layer.child("obj")
                if not obj:
                    continue
                for entry in obj.children():
                    if scalar(entry, "oS") != "bossLimbo":
                        continue
                    path = "/".join(str(scalar(entry, key, "")) for key in ["l0", "l1", "l2"])
                    resource_node = obj_root.get(path)
                    resource = self.export_map_resource(f"obj/{path}", resource_node) if resource_node else None
                    if resource:
                        z = int(map_layer.name) * 100 + int(scalar(entry, "z", 0) or 0)
                        layers.append(self.layer_manifest("obj", entry, resource, z))

            minimap = root.get("miniMap/canvas")
            minimap_src = None
            if isinstance(minimap, WzCanvasProperty):
                target = self.output / "assets" / "maps" / f"{map_id}-minimap.png"
                self.save_canvas(minimap, target)
                minimap_src = str(target.relative_to(self.output))
            exported.append(
                {
                    **stage,
                    "bgm": scalar(info, "bgm", ""),
                    "mode": scalar(info, "mode", "hard"),
                    "vr": vr,
                    "dimensions": [vr[2] - vr[0], vr[3] - vr[1]],
                    "minimap": minimap_src,
                    "layers": sorted(layers, key=lambda item: item["z"]),
                }
            )
        return exported

    @staticmethod
    def layer_manifest(kind: str, entry, resource: dict, z: int) -> dict:
        return {
            "kind": kind,
            "x": int(scalar(entry, "x", 0) or 0),
            "y": int(scalar(entry, "y", 0) or 0),
            "flip": bool(scalar(entry, "f", 0)),
            "z": z,
            "animation": scalar(entry, "spineAni"),
            "spineName": scalar(entry, "spineName"),
            "timeScale": int(scalar(entry, "timeScale", 100) or 100),
            **resource,
        }

    def export_mobs(self) -> list[dict]:
        mobs = []
        for stage_id, mob_ids in MOBS_BY_STAGE.items():
            for mob_id in mob_ids:
                image_path = self.source / "Mob" / "_Canvas" / f"{mob_id}.img"
                if not image_path.exists():
                    continue
                root = self.load(f"Mob/_Canvas/{mob_id}.img").root
                actions = []
                for child in root.children():
                    sequence = self.export_sequence(child, "mobs", f"{mob_id}/{child.name}", max_edge=1400)
                    if sequence:
                        actions.append(sequence)
                mobs.append(
                    {
                        "id": mob_id,
                        "label": MOB_LABELS.get(mob_id, mob_id),
                        "stage": stage_id,
                        "actions": actions,
                        "sourceBytes": image_path.stat().st_size,
                    }
                )
        return mobs

    def pattern_stage(self, path: str) -> str:
        group = path.split("/", 1)[0]
        if group == "common":
            return "all"
        value = int(group) if group.isdigit() else 0
        if 1010 <= value <= 1018:
            return "p1"
        if 1019 <= value <= 1024:
            return "p2c"
        if 1026 <= value <= 1029:
            return "p2d"
        if 1031 <= value <= 1036:
            return "p3"
        return "all"

    def export_patterns(self) -> list[dict]:
        root = self.load("Mob/BossPattern/_Canvas/BossLimbo.img").root
        patterns = []

        def walk(node, path=""):
            sequence = self.export_sequence(node, "patterns", path, max_edge=1368) if path else None
            if sequence:
                width = sequence["bounds"][2] - sequence["bounds"][0]
                height = sequence["bounds"][3] - sequence["bounds"][1]
                sequence.update(
                    {
                        "stage": self.pattern_stage(path),
                        "fullScreen": width >= 1000 or height >= 700 or "/screen" in f"/{path.lower()}",
                    }
                )
                patterns.append(sequence)
            for child in node.children():
                if isinstance(child, WzSubProperty) and not isinstance(child, WzCanvasProperty):
                    walk(child, f"{path}/{child.name}" if path else child.name)

        walk(root)
        return patterns

    def export_video_inventory(self, patterns: list[dict]) -> dict:
        video_dir = ROOT / "clien" / "Data" / "Video"
        existing = [
            {"name": path.name, "bytes": path.stat().st_size}
            for path in sorted(video_dir.glob("*.mcv"))
        ]
        candidates = [
            {"path": pattern["path"], "frames": pattern["sourceFrameCount"], "stage": pattern["stage"]}
            for pattern in patterns
            if pattern["fullScreen"]
        ]
        return {
            "nativeCanvasVideoCount": 0,
            "existingMcv": existing,
            "limboMcvCandidates": candidates,
            "playbackConstraint": "当前客户端 MCV 为单实例播放通道；林波转场与五/六转技能同时触发时会抢占或中断。",
        }

    def copy_site(self):
        template_dir = Path(__file__).with_name("limbo-preview-site")
        for name in ["index.html", "styles.css", "app.js"]:
            shutil.copy2(template_dir / name, self.output / name)
        vendor_source = next(Path("/tmp").glob("limbo-spine.*/node_modules/@esotericsoftware/spine-player"), None)
        if not vendor_source:
            raise FileNotFoundError("Spine Player 4.1 runtime not found under /tmp/limbo-spine.*")
        vendor = self.output / "vendor"
        vendor.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vendor_source / "dist" / "iife" / "spine-player.min.js", vendor / "spine-player.min.js")
        shutil.copy2(vendor_source / "dist" / "spine-player.css", vendor / "spine-player.css")
        shutil.copy2(vendor_source / "LICENSE", vendor / "LICENSE")
        serve = self.output / "serve-preview.sh"
        serve.write_text(
            "#!/bin/zsh\ncd \"${0:A:h}\"\npython3 -m http.server 8765\n",
            encoding="utf-8",
        )
        serve.chmod(0o755)

    def run(self):
        self.output.mkdir(parents=True, exist_ok=True)
        maps = self.export_maps()
        mobs = self.export_mobs()
        patterns = self.export_patterns()
        manifest = {
            "title": "林波困难模式资源完整性预览",
            "source": str(self.source),
            "classificationNote": "BossPattern 未附技能阶段元数据；1010–1018、1019–1024、1026–1029、1031–1036 按资源编号初步归入 P1、P2-C、P2-D、P3，common 为全阶段。",
            "maps": maps,
            "mobs": mobs,
            "patterns": patterns,
            "spines": list(self.spines.values()),
            "objectSequences": list(self.object_sequences.values()),
            "video": self.export_video_inventory(patterns),
            "quick": self.quick,
        }
        (self.output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.output / "data.js").write_text(
            "window.LIMBO_MANIFEST = " + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + ";\n",
            encoding="utf-8",
        )
        self.copy_site()
        print(
            json.dumps(
                {
                    "output": str(self.output),
                    "maps": len(maps),
                    "mobs": len(mobs),
                    "patterns": len(patterns),
                    "spines": len(self.spines),
                    "quick": self.quick,
                },
                ensure_ascii=False,
            )
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_TMS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--quick", action="store_true", help="export at most eight frames per animation")
    args = parser.parse_args()
    Exporter(args.source, args.output, args.quick).run()


if __name__ == "__main__":
    main()
