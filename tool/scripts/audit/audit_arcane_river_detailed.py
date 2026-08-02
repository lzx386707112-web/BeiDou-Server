#!/usr/bin/env python3
"""Produce a per-map, source-to-target Arcane River compatibility report."""

from __future__ import annotations

import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(ROOT / "tool" / "scripts" / "migration"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSoundProperty, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.writer import _read_sound_payload  # noqa: E402

import migrate_arcane_river_fields as migration  # noqa: E402


CLIENT = ROOT / "clien" / "Data"
REPORT = ROOT / "docs" / "migrations" / "arcane-river-detailed-audit.md"
SECTIONS = ("info", "back", "portal", "life", "obj", "tile", "ladderRope")
REGION_NAMES = {
    "450001": "消逝的旅途",
    "450002": "啾啾岛",
    "450003": "梦都拉克兰",
    "450005": "阿尔卡娜",
    "450006": "莫拉斯",
    "450007": "埃斯佩拉",
}


@dataclass
class Result:
    map_id: int
    errors: list[str] = field(default_factory=list)
    source_objects: int = 0
    target_objects: int = 0
    source_backs: int = 0
    target_backs: int = 0
    source_life: int = 0
    target_life: int = 0
    portals: int = 0
    branches: int = 0
    canvases: int = 0
    decoded_bytes: int = 0
    npc_count: int = 0
    mob_count: int = 0


class DetailedAudit:
    def __init__(self) -> None:
        self.gms_cache: dict[Path, WzImage] = {}
        self.bms_cache: dict[Path, WzImage] = {}
        self.branch_cache: dict[tuple[Path, str], tuple[list[str], int, int]] = {}
        self.legacy_fields = {section: set() for section in SECTIONS}
        self.results: list[Result] = []
        self.legacy_header = self.gms(CLIENT / "Sound/Bgm12.img").root.get("AquaCave").header

    def load(self, path: Path, key: WzKey, cache: dict[Path, WzImage]) -> WzImage:
        if path not in cache:
            image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
            image.parse()
            cache[path] = image
        return cache[path]

    def gms(self, path: Path) -> WzImage:
        return self.load(path, migration.GMS_KEY, self.gms_cache)

    def bms(self, path: Path) -> WzImage:
        return self.load(path, migration.BMS_KEY, self.bms_cache)

    @staticmethod
    def fields(node) -> set[str]:
        return {child.name for child in node.children()} if node is not None else set()

    def build_legacy_baseline(self) -> int:
        installed = {str(map_id) for map_id in migration.MAP_IDS}
        parsed = 0
        for path in (CLIENT / "Map/Map").glob("Map[0-9]/*.img"):
            if path.parent.name == "Map4" and path.stem in installed:
                continue
            try:
                image = self.gms(path)
            except Exception:  # pre-existing unrelated malformed maps are not this pack's baseline
                continue
            parsed += 1
            self.legacy_fields["info"].update(self.fields(image.root.child("info")))
            for section in ("back", "portal", "life", "ladderRope"):
                root = image.root.child(section)
                if root is not None:
                    for entry in root.children():
                        self.legacy_fields[section].update(self.fields(entry))
            for layer in [child for child in image.root.children() if child.name.isdigit()]:
                for section in ("obj", "tile"):
                    root = layer.child(section)
                    if root is not None:
                        for entry in root.children():
                            self.legacy_fields[section].update(self.fields(entry))
        self.gms_cache.clear()
        return parsed

    @staticmethod
    def section_count(image: WzImage, section: str) -> int:
        if section in {"obj", "tile"}:
            return sum(
                len(root.children())
                for layer in [child for child in image.root.children() if child.name.isdigit()]
                if (root := layer.child(section)) is not None
            )
        root = image.root.child(section)
        return len(root.children()) if root is not None else 0

    def compare_schema(self, image: WzImage, result: Result) -> None:
        extra_roots = {child.name for child in image.root.children()} - migration.MAP_ROOTS
        if extra_roots:
            result.errors.append(f"旧端基线外根节点: {sorted(extra_roots)}")
        extra_info = self.fields(image.root.child("info")) - self.legacy_fields["info"]
        if extra_info:
            result.errors.append(f"旧端基线外 info 字段: {sorted(extra_info)}")
        if result.map_id in migration.LEGACY_ZERO_FIELD_LIMIT_MAPS and migration.child_value(
            image.root.child("info"), "fieldLimit"
        ) != 0:
            result.errors.append("info/fieldLimit 未降级为旧端安全值 0")
        foothold = image.root.child("foothold")
        if foothold is not None:
            for node, path in migration.walk(foothold):
                remaining = self.fields(node) & migration.FOOTHOLD_UNSUPPORTED_BY_MAP.get(
                    result.map_id, set()
                )
                if remaining:
                    result.errors.append(f"旧端不兼容 foothold/{path}: {sorted(remaining)}")
        for section in ("back", "portal", "life", "ladderRope"):
            root = image.root.child(section)
            if root is None:
                continue
            for entry in root.children():
                extra = self.fields(entry) - self.legacy_fields[section]
                if extra:
                    result.errors.append(f"旧端基线外 {section}/{entry.name}: {sorted(extra)}")
                if section == "life":
                    unsupported = migration.LIFE_UNSUPPORTED_BY_MAP.get(result.map_id, set())
                    remaining = self.fields(entry) & unsupported
                    if remaining:
                        result.errors.append(
                            f"旧端不兼容 life/{entry.name}: {sorted(remaining)}"
                        )
        for layer in [child for child in image.root.children() if child.name.isdigit()]:
            for section in ("obj", "tile"):
                root = layer.child(section)
                if root is None:
                    continue
                if section == "obj" and result.map_id in migration.LEGACY_CONNECT_FIRST_MAPS:
                    entries = list(root.children())
                    connect_count = sum(
                        migration.child_value(entry, "oS") == "connect" for entry in entries
                    )
                    if connect_count and (
                        any(
                            migration.child_value(entry, "oS") != "connect"
                            for entry in entries[:connect_count]
                        )
                        or [entry.name for entry in entries]
                        != [str(index) for index in range(len(entries))]
                    ):
                        result.errors.append(
                            f"旧端 connect 顺序或编号不稳定: {layer.name}/obj"
                        )
                for entry in root.children():
                    extra = self.fields(entry) - self.legacy_fields[section]
                    if extra:
                        result.errors.append(
                            f"旧端基线外 {layer.name}/{section}/{entry.name}: {sorted(extra)}"
                        )

    @staticmethod
    def normalized_xml(text: str) -> bytes:
        return ET.tostring(ET.fromstring(text), encoding="utf-8")

    def compare_source_and_server(self, map_id: int, target: WzImage, result: Result) -> None:
        target_xml = migration.image_to_xml(target, f"{map_id}.img")
        expected_sha = migration.PINNED_CLIENT_MAP_SHA256.get(map_id)
        if expected_sha:
            target_path = CLIENT / f"Map/Map/Map4/{map_id}.img"
            if hashlib.sha256(target_path.read_bytes()).hexdigest() != expected_sha:
                result.errors.append("客户端 IMG 不等于实机验证固定版本")
        else:
            source_path = migration.SOURCE / f"Map/Map/Map4/{map_id}.img"
            expected, _ = migration.clone_image(
                source_path, lambda root: migration.sanitize_map(root, map_id)
            )
            expected_xml = migration.image_to_xml(expected, f"{map_id}.img")
            if self.normalized_xml(expected_xml) != self.normalized_xml(target_xml):
                result.errors.append("客户端语义树不等于迁移规则处理后的 TMS 源树")
        normalized_target = self.normalized_xml(target_xml)
        trees = ["wz"]
        if (ROOT / "gms-server/wz-zh-CN/Map.wz").exists():
            trees.append("wz-zh-CN")
        for tree in trees:
            path = ROOT / f"gms-server/{tree}/Map.wz/Map/Map4/{map_id}.img.xml"
            if not path.exists():
                result.errors.append(f"缺少 {tree} 地图 XML")
                continue
            if self.normalized_xml(path.read_text(encoding="utf-8")) != normalized_target:
                result.errors.append(f"{tree} 地图 XML 与客户端语义树不一致")

    def canvas_metrics(self, node, label: str) -> tuple[list[str], int, int]:
        errors: list[str] = []
        count = 0
        decoded_bytes = 0
        for child, prop_path in migration.walk(node):
            if child.name in {"_outlink", "_inlink"}:
                errors.append(f"{label}/{prop_path} 残留链接")
            if not isinstance(child, WzCanvasProperty):
                continue
            count += 1
            width, height = int(child.width), int(child.height)
            decoded_bytes += width * height * 2
            if int(child.format) + int(child.format2) != 1:
                errors.append(f"{label}/{prop_path} 非 ARGB4444")
            if width <= 0 or height <= 0 or max(width, height) > migration.MAX_CANVAS_EDGE:
                errors.append(f"{label}/{prop_path} 尺寸 {width}x{height}")
            try:
                decode_canvas(child, region="GMS")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{label}/{prop_path} 解码失败: {exc}")
        return errors, count, decoded_bytes

    def branch_metrics(self, path: Path, branch: str) -> tuple[list[str], int, int]:
        key = (path, branch)
        if key in self.branch_cache:
            return self.branch_cache[key]
        image = self.gms(path)
        node = image.root.get(branch)
        if node is None:
            value = ([f"缺少资源 {path.relative_to(CLIENT)}/{branch}"], 0, 0)
        else:
            value = self.canvas_metrics(node, f"{path.relative_to(CLIENT)}/{branch}")
            if value[1] == 0:
                value[0].append(f"资源分支无 Canvas: {path.relative_to(CLIENT)}/{branch}")
        self.branch_cache[key] = value
        return value

    def check_references(self, image: WzImage, result: Result) -> None:
        dependencies = migration.collect_dependencies(image)
        result.npc_count = len(dependencies["npcs"])
        result.mob_count = len(dependencies["mobs"])
        errors, canvases, decoded_bytes = self.canvas_metrics(
            image.root, f"Map/Map/Map4/{result.map_id}.img"
        )
        result.errors.extend(errors)
        result.canvases += canvases
        result.decoded_bytes += decoded_bytes
        swim = migration.child_value(image.root.child("info"), "swim")
        expected_swim = 1 if result.map_id in migration.LEGACY_SWIM_MAPS else 0
        if swim != expected_swim:
            result.errors.append(
                f"info/swim={swim}，旧端兼容期望值={expected_swim}"
            )
        for (kind, name), branches in dependencies["assets"].items():
            path = CLIENT / f"Map/{kind}/{name}.img"
            if not path.exists():
                result.errors.append(f"缺少资源 IMG: Map/{kind}/{name}.img")
                continue
            asset_image = self.gms(path)
            for error in migration.legacy_asset_structure_errors(asset_image, kind, name):
                result.errors.append(f"资源数字子节点不连续: {error}")
            for branch in branches:
                result.branches += 1
                branch_errors, branch_canvases, branch_bytes = self.branch_metrics(path, branch)
                result.errors.extend(branch_errors)
                result.canvases += branch_canvases
                result.decoded_bytes += branch_bytes
        helper = self.gms(CLIENT / "Map/MapHelper.img")
        for mark in dependencies["marks"]:
            node = helper.root.get(f"mark/{mark}")
            if node is None:
                result.errors.append(f"缺少 mapMark: {mark}")
            else:
                mark_errors, mark_canvases, mark_bytes = self.canvas_metrics(
                    node, f"Map/MapHelper.img/mark/{mark}"
                )
                result.errors.extend(mark_errors)
                result.canvases += mark_canvases
                result.decoded_bytes += mark_bytes
        for bgm in dependencies["bgms"]:
            pack, name = bgm.split("/", 1)
            path = CLIENT / f"Sound/{pack}.img"
            sound = self.gms(path).root.get(name) if path.exists() else None
            if not isinstance(sound, WzSoundProperty):
                result.errors.append(f"缺少 BGM: {bgm}")
            elif sound.header != self.legacy_header or not migration.is_legacy_mp3_payload(
                _read_sound_payload(sound)
            ):
                result.errors.append(f"BGM 非旧端 22.05kHz MPEG-2 64kbps 双声道规格: {bgm}")
        for npc_id in dependencies["npcs"]:
            path = CLIENT / f"Npc/{npc_id:07d}.img"
            if not path.exists():
                result.errors.append(f"缺少 NPC: {npc_id}")
            else:
                info = self.gms(path).root.child("info")
                unsupported = self.fields(info) & migration.NPC_INFO_UNSUPPORTED
                if unsupported:
                    result.errors.append(f"NPC {npc_id} 旧端基线外字段: {sorted(unsupported)}")
                for child in self.gms(path).root.children():
                    suffix = child.name.removeprefix(migration.NPC_ROOT_UNSUPPORTED_PREFIX)
                    if (
                        child.name.startswith(migration.NPC_ROOT_UNSUPPORTED_PREFIX)
                        and suffix.isdigit()
                    ):
                        result.errors.append(f"NPC {npc_id} 残留现代条件动作: {child.name}")
            if str(npc_id).startswith("300") and not (
                ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml"
            ).exists():
                result.errors.append(f"缺少服务端 NPC: {npc_id}")
        for mob_id in dependencies["mobs"]:
            path = CLIENT / f"Mob/{mob_id:07d}.img"
            if not path.exists():
                result.errors.append(f"缺少 Mob: {mob_id}")
            else:
                info = self.gms(path).root.child("info")
                unsupported = self.fields(info) & migration.MOB_INFO_UNSUPPORTED
                if unsupported:
                    result.errors.append(f"Mob {mob_id} 旧端基线外字段: {sorted(unsupported)}")
                if migration.child_value(info, "eva") != 200:
                    result.errors.append(f"Mob {mob_id} 客户端 eva 非 200")
            server_mob = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
            if not server_mob.exists():
                result.errors.append(f"缺少服务端 Mob: {mob_id}")
            else:
                server_info = next(
                    (child for child in ET.parse(server_mob).getroot() if child.get("name") == "info"),
                    None,
                )
                server_eva = next(
                    (child.get("value") for child in server_info or [] if child.get("name") == "eva"),
                    None,
                )
                if server_eva != "200":
                    result.errors.append(f"Mob {mob_id} 服务端 eva 非 200")
        self.check_portals(image, result)

    def check_portals(self, image: WzImage, result: Result) -> None:
        portal = image.root.child("portal")
        result.portals = len(portal.children()) if portal else 0
        if portal is None:
            result.errors.append("缺少 portal 根节点")
            return
        for entry in portal.children():
            portal_type = migration.child_value(entry, "pt")
            if portal_type not in {0, 1, 2, 3, 6, 7, 10}:
                result.errors.append(f"Portal {entry.name} 类型不在旧端样本: {portal_type}")
            target = migration.child_value(entry, "tm")
            target_name = str(migration.child_value(entry, "tn") or "")
            if not isinstance(target, int) or target == 999999999:
                continue
            if target not in migration.MAP_ID_SET:
                result.errors.append(f"Portal {entry.name} 指向未安装地图 {target}")
                continue
            target_image = self.gms(CLIENT / f"Map/Map/Map4/{target}.img")
            target_root = target_image.root.child("portal")
            names = {
                str(migration.child_value(candidate, "pn"))
                for candidate in target_root.children()
                if migration.child_value(candidate, "pn") is not None
            }
            if target_name and target_name not in names:
                result.errors.append(f"Portal {entry.name} 落点不存在: {target}/{target_name}")

    def check_map(self, map_id: int) -> Result:
        result = Result(map_id)
        source = self.bms(migration.SOURCE / f"Map/Map/Map4/{map_id}.img")
        target = self.gms(CLIENT / f"Map/Map/Map4/{map_id}.img")
        result.source_objects = self.section_count(source, "obj")
        result.target_objects = self.section_count(target, "obj")
        result.source_backs = self.section_count(source, "back")
        result.target_backs = self.section_count(target, "back")
        result.source_life = self.section_count(source, "life")
        result.target_life = self.section_count(target, "life")
        self.compare_schema(target, result)
        self.compare_source_and_server(map_id, target, result)
        self.check_references(target, result)
        return result

    def write_report(self, baseline_count: int) -> None:
        error_maps = [result for result in self.results if result.errors]
        lines = [
            "# 神秘河六区逐图兼容审计",
            "",
            f"- 旧端结构基线：{baseline_count} 张现有地图",
            f"- 检查地图：{len(self.results)} 张",
            f"- 通过：{len(self.results) - len(error_maps)} 张",
            f"- 失败：{len(error_maps)} 张",
            "- 检查维度：TMS 源树一致性、旧端字段基线、服务端有效 Map 树 XML、Portal 落点、"
            "Back/Obj/Tile 分支、connect 顺序与连续编号、MapHelper、NPC/Mob、"
            "ARGB4444、BGM MPEG-2 22.05kHz。",
            "",
            "| 地图 | 区域 | Obj 源→目标 | Back 源→目标 | Life 源→目标 | Portal | 资源分支 | Canvas | 保守纹理 MiB | 结果 |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        for result in self.results:
            region = REGION_NAMES[str(result.map_id)[:6]]
            status = "PASS" if not result.errors else f"FAIL({len(result.errors)})"
            lines.append(
                f"| {result.map_id} | {region} | {result.source_objects}→{result.target_objects} | "
                f"{result.source_backs}→{result.target_backs} | {result.source_life}→{result.target_life} | "
                f"{result.portals} | {result.branches} | {result.canvases} | "
                f"{result.decoded_bytes / 1048576:.2f} | {status} |"
            )
        if error_maps:
            lines.extend(["", "## 错误明细", ""])
            for result in error_maps:
                lines.append(f"### {result.map_id}")
                lines.extend(f"- {error}" for error in result.errors)
                lines.append("")
        migration.atomic_write_text(REPORT, "\n".join(lines) + "\n")

    def run(self) -> int:
        baseline_count = self.build_legacy_baseline()
        print(f"legacy baseline maps: {baseline_count}")
        for index, map_id in enumerate(migration.MAP_IDS, 1):
            result = self.check_map(map_id)
            self.results.append(result)
            print(
                f"[{index:03d}/{len(migration.MAP_IDS):03d}] {map_id}: "
                f"{'PASS' if not result.errors else 'FAIL'}"
            )
        self.write_report(baseline_count)
        errors = sum(len(result.errors) for result in self.results)
        print(f"report: {REPORT}")
        print(f"result: maps={len(self.results)} errors={errors}")
        return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(DetailedAudit().run())
