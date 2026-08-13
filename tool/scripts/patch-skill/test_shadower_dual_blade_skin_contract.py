#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
WZPY = ROOT / "tool" / "wz-python"
import sys
sys.path[:0] = [str(PATCH_SKILL), str(WZPY)]

import patch_shadower_dual_blade_skin as migration  # noqa: E402
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty, WzUolProperty  # noqa: E402


EXPECTED_CANVAS_COUNTS = {
    (4201004, "effect"): 11,
    (4201004, "hit"): 4,
    (4201005, "effect"): 14,
    (4201005, "hit"): 14,
    (4211002, "effect"): 9,
    (4211002, "hit"): 4,
    (4211004, "effect"): 14,
    (4211004, "effect0"): 14,
    (4211004, "hit"): 5,
    (4211006, "effect"): 13,
    (4211006, "hit"): 4,
    (4221001, "effect"): 10,
    (4221001, "special"): 5,
    (4221003, "effect"): 8,
    (4221003, "hit"): 3,
    (4221003, "ball"): 3,
    (4221003, "mob"): 7,
    (4221004, "effect"): 8,
    (4221004, "mob0"): 4,
    (4221007, "effect"): 8,
    (4221007, "hit"): 5,
}


def git_blob(path: str, revision: str = "HEAD") -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{revision}:{path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def parsed(data: bytes, name: str):
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise AssertionError(f"malformed {name}: {image.parse_warnings}")
    return root


def property_signature(node):
    if node is None:
        return None
    if isinstance(node, WzCanvasProperty):
        origin = node.child("origin")
        delay = node.child("delay")
        return (
            node.name, node.width, node.height,
            (origin.x, origin.y) if origin is not None else None,
            int(delay.value) if delay is not None else None,
        )
    if isinstance(node, WzSubProperty):
        return (node.name, tuple(property_signature(child) for child in node.children()))
    return (node.name, node.value)


def canvas_signatures(node):
    result = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, WzCanvasProperty):
            origin = current.child("origin")
            delay = current.child("delay")
            result.append((
                current.name, current.width, current.height,
                (origin.x, origin.y) if origin is not None else None,
                int(delay.value) if delay is not None else None,
            ))
        elif hasattr(current, "children"):
            stack.extend(reversed(current.children()))
    return result


def raw_skill_layout(data: bytes, name: str):
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=name)
    _, _, names, spans = migration.locate_skill_records(image, data, Path(name))
    return {
        record_name: ((start, end), data[start:end])
        for record_name, (start, end) in zip(names, spans)
    }


def raw_root_layout(data: bytes, name: str):
    image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=name)
    count_offset, count_size, names, spans = migration.locate_root_records(
        image, data, Path(name)
    )
    records = {
        record_name: ((start, end), data[start:end])
        for record_name, (start, end) in zip(names, spans)
    }
    return count_offset, count_size, names, records


class ShadowerDualBladeSkinContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_roots = {}
        cls.baseline_roots = {}
        for book in (420, 421, 422):
            path = ROOT / f"clien/Data/Skill/{book}.img"
            cls.client_roots[book] = parsed(path.read_bytes(), path.name)
            cls.baseline_roots[book] = parsed(
                git_blob(
                    f"clien/Data/Skill/{book}.img", migration.LEGACY_BASELINE
                ),
                f"baseline-{book}.img",
            )
        cls.client_string = parsed(
            (ROOT / "clien/Data/String/Skill.img").read_bytes(), "String/Skill.img"
        )
        cls.server_string = ET.parse(
            ROOT / "gms-server/wz/String.wz/Skill.img.xml"
        ).getroot()

    def test_source_and_icon_hashes_are_pinned(self):
        self.assertEqual("https://maplestory.io/api/wz/TMS/209/Skill", migration.TMS_API)
        self.assertEqual(
            {spec.source_id for spec in migration.SKINS},
            set(migration.ICON_PIXEL_HASHES),
        )

    def test_character_actions_remain_at_git_baseline(self):
        for spec in migration.SKINS:
            book = spec.target_id // 10000
            actual = self.client_roots[book].get(f"skill/{spec.target_id}/action")
            expected = self.baseline_roots[book].get(f"skill/{spec.target_id}/action")
            self.assertEqual(property_signature(expected), property_signature(actual), spec.target_id)

    def test_legacy_second_job_support_skills_are_restored_byte_for_byte(self):
        path = ROOT / "clien/Data/Skill/420.img"
        actual_data = path.read_bytes()
        baseline_data = migration.git_blob(
            migration.LEGACY_BASELINE, "clien/Data/Skill/420.img"
        )
        for data, label in ((actual_data, "actual"), (baseline_data, "baseline")):
            image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=label)
            image.parse()
            _, _, names, spans = migration.locate_skill_records(image, data, path)
            records = {name: data[start:end] for name, (start, end) in zip(names, spans)}
            if label == "actual":
                actual_records = records
            else:
                baseline_records = records
        for skill_id in migration.LEGACY_AUXILIARY_SKILLS:
            self.assertEqual(
                baseline_records[str(skill_id)], actual_records[str(skill_id)], skill_id
            )

    def test_only_approved_client_skill_records_changed(self):
        for book in (420, 421, 422):
            path = ROOT / f"clien/Data/Skill/{book}.img"
            actual_data = path.read_bytes()
            generated_data = migration.patch_client_skill_book(
                book, migration.SKINS_BY_BOOK[book], {}, True
            )
            self.assertEqual(actual_data, generated_data, book)

    def test_visual_carrier_is_the_only_appended_root_record(self):
        for book in (420, 421, 422):
            path = ROOT / f"clien/Data/Skill/{book}.img"
            actual = raw_root_layout(path.read_bytes(), path.name)
            self.assertEqual(("info", "skill", migration.CARRIER_NAME), actual[2], book)
            self.assertEqual(migration.CARRIER_NAME, actual[2][-1], book)

    def test_changed_string_records_keep_their_original_spans(self):
        path = ROOT / "clien/Data/String/Skill.img"
        actual = raw_root_layout(path.read_bytes(), path.name)[3]
        baseline = raw_root_layout(
            git_blob("clien/Data/String/Skill.img"), "HEAD-String-Skill.img"
        )[3]
        for spec in migration.SKINS:
            name = str(spec.target_id)
            self.assertEqual(baseline[name][0], actual[name][0], (name, "span"))

    def test_attack_parameters_remain_at_the_approved_skin_values(self):
        for spec in migration.ATTACK_SPECS:
            book = spec.target_id // 10000
            target = self.client_roots[book].get(f"skill/{spec.target_id}")
            self.assertEqual(
                migration.ATTACK_PARAMETER_HASHES[spec.target_id],
                migration.attack_parameter_hash(target, spec),
                spec.target_id,
            )

    def test_complete_level_contract_remains_at_legacy_baseline(self):
        for skin in migration.SKINS:
            book = skin.target_id // 10000
            actual_levels = self.client_roots[book].get(
                f"skill/{skin.target_id}/level"
            )
            baseline_levels = self.baseline_roots[book].get(
                f"skill/{skin.target_id}/level"
            )
            self.assertEqual(
                tuple(level.name for level in baseline_levels.children()),
                tuple(level.name for level in actual_levels.children()),
                skin.target_id,
            )
            for baseline_level, actual_level in zip(
                baseline_levels.children(), actual_levels.children()
            ):
                baseline_values = {
                    child.name: property_signature(child)
                    for child in baseline_level.children()
                }
                actual_values = {
                    child.name: property_signature(child)
                    for child in actual_level.children()
                }
                self.assertEqual(
                    baseline_values,
                    actual_values,
                    (skin.target_id, baseline_level.name),
                )

    def test_all_attack_skills_are_dagger_only(self):
        for spec in migration.ATTACK_SPECS:
            book = spec.target_id // 10000
            client = self.client_roots[book].get(f"skill/{spec.target_id}")
            self.assertEqual(33, migration.int_value(client, "weapon"), spec.target_id)
            self.assertIsNone(client.child("subWeapon"), spec.target_id)

            server = ET.parse(
                ROOT / f"gms-server/wz/Skill.wz/{book}.img.xml"
            ).getroot()
            server_skill = server.find(
                f"./imgdir[@name='skill']/imgdir[@name='{spec.target_id}']"
            )
            weapon = server_skill.find("./int[@name='weapon']")
            self.assertIsNotNone(weapon, spec.target_id)
            self.assertEqual("33", weapon.get("value"), spec.target_id)
            self.assertIsNone(server_skill.find("./*[@name='subWeapon']"), spec.target_id)

    def test_server_level_parameters_match_client(self):
        for book in (420, 421, 422):
            server = ET.parse(ROOT / f"gms-server/wz/Skill.wz/{book}.img.xml").getroot()
            skills = server.find("./imgdir[@name='skill']")
            for spec in (item for item in migration.ATTACK_SPECS if item.target_id // 10000 == book):
                client_levels = self.client_roots[book].get(f"skill/{spec.target_id}/level")
                server_skill = skills.find(f"./imgdir[@name='{spec.target_id}']")
                for client_level in client_levels.children():
                    server_level = server_skill.find(
                        f"./imgdir[@name='level']/imgdir[@name='{client_level.name}']"
                    )
                    client_values = {
                        child.name: property_signature(child)[1:]
                        for child in client_level.children()
                    }
                    server_values = {
                        child.get("name"): (
                            (int(child.get("x")), int(child.get("y")))
                            if child.tag == "vector"
                            else int(child.get("value"))
                            if child.tag in ("int", "short", "long")
                            else child.get("value")
                        )
                        for child in server_level
                    }
                    normalized_client = {
                        name: value[0] if len(value) == 1 else value
                        for name, value in client_values.items()
                    }
                    self.assertEqual(
                        normalized_client, server_values,
                        (spec.target_id, client_level.name),
                    )

    def test_visuals_are_aligned_visible_argb4444_and_non_cyclic(self):
        for spec in migration.SKINS:
            book = spec.target_id // 10000
            target = self.client_roots[book].get(f"skill/{spec.target_id}")
            pad = target.child(migration.PAD_NAME)
            self.assertIsInstance(pad, WzUolProperty)
            self.assertEqual("level", pad.value)
            self.assertIsNotNone(migration.resolve_uol(pad))
            carrier = self.client_roots[book].get(
                f"{migration.CARRIER_NAME}/{spec.target_id}"
            )
            self.assertEqual(
                migration.ALIGNMENT_VERSION,
                migration.int_value(carrier, "alignmentVersion"),
            )
            for target_name, _ in spec.visuals:
                target_branch = target.child(target_name)
                self.assertIsInstance(target_branch, WzSubProperty)
                carrier_branch = carrier.child(target_name)
                self.assertEqual(
                    EXPECTED_CANVAS_COUNTS[(spec.target_id, target_name)],
                    len(canvas_signatures(carrier_branch)),
                    (spec.target_id, target_name),
                )
                if target_name == "effect" and spec.target_id in migration.EFFECT_DURATION_TARGETS:
                    direct_frames = [
                        child for child in carrier_branch.children()
                        if isinstance(child, WzCanvasProperty)
                    ]
                    duration = sum(
                        migration.int_value(frame, "delay", 100)
                        for frame in direct_frames
                    )
                    self.assertEqual(
                        migration.EFFECT_DURATION_TARGETS[spec.target_id],
                        duration,
                        spec.target_id,
                    )
                proxy_stack = [target_branch]
                proxy_frames = 0
                while proxy_stack:
                    current = proxy_stack.pop()
                    if isinstance(current, WzUolProperty):
                        resolved = migration.resolve_uol(current)
                        self.assertIsInstance(
                            resolved,
                            WzCanvasProperty,
                            (spec.target_id, target_name, current.value),
                        )
                        proxy_frames += 1
                    elif hasattr(current, "children"):
                        proxy_stack.extend(current.children())
                self.assertEqual(
                    EXPECTED_CANVAS_COUNTS[(spec.target_id, target_name)],
                    proxy_frames,
                    (spec.target_id, target_name, "proxy frames"),
                )
                stack = [carrier_branch]
                visible = False
                while stack:
                    current = stack.pop()
                    if isinstance(current, WzCanvasProperty):
                        self.assertEqual((1, 0), (current.format, current.format2))
                        with decode_canvas(current, region="GMS") as image:
                            visible = visible or image.getchannel("A").getbbox() is not None
                    if hasattr(current, "children"):
                        stack.extend(current.children())
                self.assertTrue(visible, (spec.target_id, target_name))

    def test_dual_blade_icons_replace_all_three_target_icon_states(self):
        for spec in migration.SKINS:
            book = spec.target_id // 10000
            target = self.client_roots[book].get(f"skill/{spec.target_id}")
            for name in ("icon", "iconDisabled", "iconMouseOver"):
                actual = target.child(name)
                self.assertIsInstance(actual, WzCanvasProperty)
                self.assertEqual((1, 0), (actual.format, actual.format2))
                with decode_canvas(actual, region="GMS") as image:
                    self.assertEqual((32, 32), image.size)
                    self.assertIsNotNone(image.getchannel("A").getbbox())
            self.assertEqual(
                migration.ICON_PIXEL_HASHES[spec.source_id],
                migration.embedded_icon_hash(target),
                spec.target_id,
            )

    def test_names_and_descriptions_use_simplified_chinese_dual_blade_text(self):
        descriptions = migration.build_descriptions({
            spec.target_id: self.client_roots[spec.target_id // 10000].get(
                f"skill/{spec.target_id}"
            )
            for spec in migration.SKINS
        })
        for skill_id, (skill_name, description, texts) in descriptions.items():
            client = self.client_string.child(str(skill_id))
            self.assertEqual(skill_name, client.child("name").value)
            self.assertEqual(description, client.child("desc").value)
            pad = client.child(migration.PAD_NAME)
            self.assertIsInstance(pad, WzUolProperty)
            self.assertEqual("name", pad.value)
            self.assertIsNotNone(migration.resolve_uol(pad))
            server = self.server_string.find(f"./imgdir[@name='{skill_id}']")
            server_values = {child.get("name"): child.get("value") for child in server}
            self.assertEqual(skill_name, server_values["name"])
            self.assertEqual(description, server_values["desc"])
            for name, value in texts.items():
                self.assertEqual(value, client.child(name).value)
                self.assertEqual(value, server_values[name])


if __name__ == "__main__":
    unittest.main()
