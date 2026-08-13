#!/usr/bin/env python3
"""Legacy lower-job Dual Blade experiment retained for forensic reference.

Do not run this patch in production. Shadower jobs 1-4 remain at their legacy
baseline; only the added V/VI skills are migrated in patch_explorer_other_v_vi.py.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
WZPY = ROOT / "tool" / "wz-python"
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
sys.path[:0] = [str(WZPY), str(PATCH_SKILL)]

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.writer import (  # noqa: E402
    _encode_property_list,
    encode_compressed_int,
    encode_string_block,
)

from patch_1121001_sword_illusion import (  # noqa: E402
    clone_property,
    find_imgdir_block,
    set_int,
    set_string,
)
from patch_dawn_warrior_v_vi import atomic_write_bytes, atomic_write_text  # noqa: E402


CLIENT_SKILL_DIR = ROOT / "clien" / "Data" / "Skill"
CLIENT_STRING = ROOT / "clien" / "Data" / "String" / "Skill.img"
CLIENT_CONSUME_STRING = ROOT / "clien" / "Data" / "String" / "Consume.img"
SERVER_SKILL_DIR = ROOT / "gms-server" / "wz" / "Skill.wz"
SERVER_SKILL_STRINGS = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Skill.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Skill.img.xml",
)
SERVER_CONSUME_STRINGS = (
    ROOT / "gms-server" / "wz" / "String.wz" / "Consume.img.xml",
    ROOT / "gms-server" / "wz-zh-CN" / "String.wz" / "Consume.img.xml",
)

CONSUME_STRINGS = {
    2280006: (
        "[技能册]闪光弹",
        "侠盗学#c闪光弹#，隐士学#c挑衅#",
    ),
    2290080: (
        "[能手册]闪光弹",
        "70%升至20级\\n侠盗：#c闪光弹#；隐士：#c挑衅#",
    ),
    2290081: (
        "[能手册]闪光弹",
        "50%升至30级\\n侠盗：#c闪光弹#；隐士：#c挑衅#",
    ),
    2290082: (
        "[能手册]短剑升天",
        "70%升至20级\\n侠盗：#c短剑升天#；隐士：#c忍者伏击#",
    ),
    2290083: (
        "[能手册]短剑升天",
        "50%升至30级\\n侠盗：#c短剑升天#；隐士：#c忍者伏击#",
    ),
    2290090: (
        "[能手册]短刀护佑",
        "70%升至20级\\n职业：侠盗，#c短刀护佑#5级以上",
    ),
    2290091: (
        "[能手册]短刀护佑",
        "50%升至30级\\n职业：侠盗，#c短刀护佑#15级以上",
    ),
    2290092: (
        "[能手册]幻影箭",
        "70%升至20级\\n#c幻影箭#5级以上",
    ),
    2290093: (
        "[能手册]幻影箭",
        "50%升至30级\\n#c幻影箭#15级以上",
    ),
}

TMS_API = "https://maplestory.io/api/wz/TMS/209/Skill"
LEGACY_BASELINE = "db6b6b4a51"
LEGACY_AUXILIARY_SKILLS = (4201002, 4201003)

CARRIER_NAME = "dualBladeSkin"
PAD_NAME = "_skinPad"
ALIGNMENT_VERSION = 2
ICON_API = TMS_API

LEGACY_ICON_PNG_HASHES = {
    4301002: {
        "icon": "0afb81045269e5c78be10d689fec7710ade94197990f481cede6958dded692d2",
        "iconDisabled": "3e13a40c8f0a022104e049295bf0d01fc12e842f74321adad501a759dc39e97d",
        "iconMouseOver": "633d976f1fc4bfb997fb1f4d90e572a265fcbe45947b8f5b2265136569ea52d4",
    },
    4311001: {
        "icon": "c54368b941def7258747f85e49447fab26375844d016d4bdf4df49acd8705ca3",
        "iconDisabled": "8160206664753e4d139e6931f8494f7404a1d76448d5179d77916e8f2cee10e6",
        "iconMouseOver": "c372f4be6014c9cb4988658e8000665c510209713711e671f63714fff5e2eba9",
    },
    4301001: {
        "icon": "44abf90ffe5094b694304120126571e7f27dc4c1f1e05919f7bca9d379004630",
        "iconDisabled": "a7ce25925c1519f98ba385b2b0fbe7ef78fb7d71ed265540f5a382fd61d5d5bc",
        "iconMouseOver": "59aa8c02bfb99e1ff666d927363c6837d19a808d3696105f9d3b9ab8b795b484",
    },
    4311002: {
        "icon": "e5f95fe245aef9892bba4173ee20f48aac16fb4707948e6032ccbd0c732f99aa",
        "iconDisabled": "06ba5e0705983319e2bbcb8c9646ad78b9b19ba973fca5016c7e3e1bf4fe20a8",
        "iconMouseOver": "2214df25e88cd9ae8dc458e6f46112e9fb25b22694f37c856d828e62af5bcac3",
    },
    4331005: {
        "icon": "677776ab7ade8b6c864ebd7b1a46d17bf0ff56ca96b3dae8542a6262973eea09",
        "iconDisabled": "51042526b0da4c8fc4063a58cdf5876789241b95bc292bbadec39253691a375b",
        "iconMouseOver": "ec84efe058fc0fb6baae5c9d8305f2530eef165fac060953baa7512030a49718",
    },
    4311003: {
        "icon": "09ffd1d869ab87ff53ae9cdebc5b73f537ffc526ac6f8dea52acf3dcc6b3e2b4",
        "iconDisabled": "9362964cfbaaef77aa28f81e9f1ef346cf99d8a588d94de509bd9502d8c793d2",
        "iconMouseOver": "d4d1e64ee584b48e5b63403312be866cd4702a141aeebfb78aa06ad5e556e90c",
    },
    4341003: {
        "icon": "922db63b6b94397a952bad5d4c760bf755a0e7737309a9ebeb07446956dbb466",
        "iconDisabled": "eec0c60e1048d4c67559d4240e9c064cc13b364ac42bae4e8be7c3ad99046e83",
        "iconMouseOver": "e217338431735fd26c5f5897a040e938be4eacbdc9c121b3fdeb237af99e775b",
    },
    4341005: {
        "icon": "c3ccfbc60f35b2b76ce7ed1ab17b649451b1f087f811998779c84141dc0d1f43",
        "iconDisabled": "9330e48ba05551603d7afc1c22d5ade107357e8d6d0a3f2da1b65c4127ae3bb1",
        "iconMouseOver": "5e8436a9e95998d61c8cfc5443074ac021b2de77f5898347cdfcbf3a76ef3c8f",
    },
    4321002: {
        "icon": "848a4768e4cfbcf03e4419912a39fd967ff4c82c9a56fe83b0cc17fc4f893e28",
        "iconDisabled": "426e352fb573a35a092187022a908773c1593884a3c41816b141bcc524d9e05e",
        "iconMouseOver": "386964f8ce0e0c0169d416ab83c7a5a799bce63a50fa6c270b9f4b7b50ec8635",
    },
    4341004: {
        "icon": "cdeb1b742a1a582e98368e9824f14ec9af52b05a5a4a74a8ab24d2e5a05824c2",
        "iconDisabled": "076578fa4b9993568e852cfd57b160a325b067181447418741be3ad404a46b74",
        "iconMouseOver": "f6aa290c39e89cf72cca83be16a51774297646a7b1c2693a86ff502f12fdd6f7",
    },
    4321001: {
        "icon": "baf534652019539d251a9d2e98af4efae2955da3af9665a99e26c5e2f2c06a12",
        "iconDisabled": "e38bbfd11fc5b99ef16057f5ed38ff29f06a1a742bb89c06d1f9843852b13331",
        "iconMouseOver": "ebeb192009b1e330f71a5ec34bcd285e92c6ce7a45c457c889f584bff209ac43",
    },
}

LEGACY_ICON_PIXEL_HASHES = {
    4301002: "8bbd90e3f5868a823b1807b5c1ff84843dead93473f7f1c62a830f6e1d47b8b9",
    4311001: "cf058492eacb3f4d68cf7d11b4b69906f2bc0515c772fae588e3f4d5eb85528c",
    4301001: "5da835a9f458617328f56bbbc10d04c22e01a272af863f59eb282b3cfb983bb8",
    4311002: "c09587a620301d6f9374435f50d609e052f6def102b9283f31cb19557f76a15d",
    4331005: "46a858d48e39034bd744efd074052ac4097eb73f0a9ed584ca1c9ebac8319f7d",
    4311003: "07d7dc8fb62c173dfc89ec2c26f8da0b08ce0767f44666e0473335c241b8dcd6",
    4341003: "a084942c6bdcb533c9426e0df298d153eef68a55dfc1ed5a5ce55cfca60ea36d",
    4341005: "a4274bc70dd798585aae0971be401aafd76bbf8b68dd076a8681e5ff8f63d187",
    4321002: "0316f9d63da1fb599bf3984c58b1c6eac9e67a350c9d7308e026cc90cd84f295",
    4341004: "6a5bd543d2fc3d5c758af2135edbad14368a8ddb75a7b65fee095aecaf190591",
    4321001: "58ffc51247de8e910458657b87c81335c69ad15140d5d3a92c17794e787a9b0e",
}

ICON_PIXEL_HASHES = {
    4301004: "58ffc51247de8e910458657b87c81335c69ad15140d5d3a92c17794e787a9b0e",
    4311002: "c09587a620301d6f9374435f50d609e052f6def102b9283f31cb19557f76a15d",
    4321004: "776ed66df3030f3bbbe0f70c4a1bc76f7cf3331970f687bd0c9a2e13a2cf26f1",
    4321006: "46a858d48e39034bd744efd074052ac4097eb73f0a9ed584ca1c9ebac8319f7d",
    4331000: "0d538b5ac0a0609d59f3cb08c90ed23d9d508177324676fc39c2ec4a997ec9f0",
    4331011: "5970e415b8d29f0e3de7476ca3e2afe41d3cadb522c2b04a52df7e9bc586a5e6",
    4341004: "4be62b4a3fc0bc0942305c5b10a2486c296ff5085f1fdf6199050cf6ed05c8cb",
    4341009: "6c92c716e27d637a0fda8073b2bee49ddae3f2c04656271289ca24647ecda965",
    4321002: "0316f9d63da1fb599bf3984c58b1c6eac9e67a350c9d7308e026cc90cd84f295",
}

EFFECT_DURATION_TARGETS = {
    4201004: 460,
    4201005: 1090,
    4211004: 700,
    4211006: 975,
    4221001: 1960,
    4221003: 1170,
    4221004: 1710,
    4221007: 900,
}

LEGACY_ATTACK_PARAMETER_HASHES = {
    4201004: "3911f8b4f928eb0c4f38b984795a12b115f87cee0423ffedacadb2baba4a0ea0",
    4201005: "cb8e7b5641274401597d30bf9095e3f6227abc8a29c9ed09df1d2df7e668a5d3",
    4211002: "c6b7e23dc5d2617c86354f79f16c0ecdbe495ec9ede0616e190cbea5d3a162e6",
    4211004: "7914e3637218fa8a6e80f9b723c61b233ef665b087877c3633baaeebe789e31f",
    4211006: "a0f2b14d1ac4d9274e1519f2e48c89489adf50399e5b46d1d09880b50c17aee3",
    4221001: "0ffd98249ac9479de4b67e815b7e4c278156630555dabe090c389fac749de0e7",
    4221003: "cdfee162b5d2069cc3ec9e1865ba427aa8eeadc5ffc17dd73f1608540f83f683",
    4221004: "533bfb39659c832c4db4d0bfcbbcb03cffee5b316c4faf75c12e8dba80b8ef3b",
    4221007: "c22e896fa5ecb115c6c5bbdc9272f68b19c8c129f7392681dcfcdf9c1ac2ef17",
}
ATTACK_PARAMETER_HASHES = LEGACY_ATTACK_PARAMETER_HASHES

ORIGIN_OFFSETS = {
    (4201004, "effect"): (-32, 8),
    (4201005, "effect"): (-21, -6),
    (4201005, "hit"): (0, -20),
    (4211002, "hit"): (14, -2),
    (4211004, "effect"): (-24, 8),
    (4211004, "hit"): (-22, 17),
    (4211006, "effect"): (-20, -24),
    (4211006, "hit"): (-2, 1),
    (4221001, "effect"): (-32, -32),
    (4221001, "special"): (-3, 27),
    (4221003, "effect"): (5, -32),
    (4221003, "hit"): (1, -3),
    (4221003, "ball"): (-2, 0),
    (4221003, "mob"): (-2, -2),
    (4221004, "effect"): (17, -32),
    (4221004, "mob0"): (4, 17),
    (4221007, "effect"): (32, 20),
    (4221007, "hit"): (5, 28),
}


@dataclass(frozen=True)
class SkinSpec:
    target_id: int
    source_book: int
    source_id: int
    source_name: str
    visuals: tuple[tuple[str, str], ...]
    remove_visuals: tuple[str, ...] = ()
    description: str = ""
    is_attack: bool = False
    damage_field: str = "damage"


SKINS = (
    SkinSpec(
        4201004, 430, 4301004, "双刃旋",
        (("effect", "effect"), ("hit", "hit")),
        ("effect0",),
        "旋转双刃，快速攻击前方多名敌人。",
        True,
    ),
    SkinSpec(
        4201005, 431, 4311002, "分身斩",
        (("effect", "effect"), ("hit", "hit")),
        description="以极快的速度连续攻击前方敌人。",
        is_attack=True,
    ),
    SkinSpec(
        4211002, 432, 4321004, "跃空斩",
        (("effect", "effect"), ("hit", "hit")),
        remove_visuals=("effect0",),
        description="跃向前方斩击多名敌人，并有一定几率使其昏迷。",
        is_attack=True,
    ),
    SkinSpec(
        4211004, 433, 4331000, "血雨暴风狂斩",
        (("effect", "effect"), ("effect0", "effect0"), ("hit", "hit")),
        description="以暴风般的连续斩击攻击前方多名敌人。",
        is_attack=True,
    ),
    SkinSpec(
        4211006, 432, 4321006, "翔空落叶斩",
        (("effect", "effect"), ("hit", "hit")),
        description="跃向前方发动旋转斩击，引爆金币攻击周围敌人。",
        is_attack=True,
        damage_field="x",
    ),
    SkinSpec(
        4221001, 434, 4341009, "幻影箭",
        (("effect", "effect"), ("special", "hit/0")),
        description="以幻影般高速的连续斩击攻击一名敌人。",
        is_attack=True,
    ),
    SkinSpec(
        4221003, 432, 4321002, "闪光弹",
        (("effect", "special"), ("hit", "hit"), ("ball", "ball"), ("mob", "mob")),
        description="投掷闪光弹攻击敌人，并使其进入挑衅状态。",
        is_attack=True,
    ),
    SkinSpec(
        4221004, 433, 4331011, "短剑升天",
        (("effect", "effect"), ("mob0", "hit/0")),
        description="以向上的短剑连斩突袭敌人，使其持续受到伤害。",
        is_attack=True,
    ),
    SkinSpec(
        4221007, 434, 4341004, "短刀护佑",
        (("effect", "effect"), ("hit", "hit")),
        description="挥舞短刀快速攻击前方多名敌人，并有一定几率使其昏迷。",
        is_attack=True,
    ),
)

ATTACK_SPECS = tuple(spec for spec in SKINS if spec.is_attack)
SKINS_BY_BOOK = {
    book: tuple(spec for spec in SKINS if spec.target_id // 10000 == book)
    for book in (420, 421, 422)
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tms_api_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "curl/8.7.1", "Accept": "application/json"},
    )
    error = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload
        except Exception as exc:  # noqa: BLE001 - retry transient API/TLS failures
            error = exc
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"TMS API request failed: {url}: {error}")


def tms_property(url: str, name: str, parent=None):
    payload = tms_api_json(url)
    prop_type = int(payload["type"])
    if prop_type == 13:
        node = WzSubProperty(name, parent)
        for child_name in payload.get("children", ()):
            if child_name in ("_hash", "_inlink", "_outlink"):
                continue
            child = tms_property(
                f"{url}/{urllib.parse.quote(str(child_name), safe='')}",
                str(child_name),
                node,
            )
            node.add(child)
        return node
    if prop_type == 12:
        png = base64.b64decode(payload["value"])
        with Image.open(io.BytesIO(png)) as decoded:
            image = decoded.convert("RGBA")
        node = WzCanvasProperty(name, parent)
        node.width, node.height = image.size
        node.format, node.format2 = 2, 0
        node._png_data = encode_canvas_payload(
            image, 2, node.width, node.height,
            key=WzKey.for_region("GMS"), listwz=False, zlib_level=9,
        )
        image.close()
        node._png_length = len(node._png_data)
        for child_name in payload.get("children", ()):
            if child_name in ("_hash", "_inlink", "_outlink"):
                continue
            node.add(tms_property(
                f"{url}/{urllib.parse.quote(str(child_name), safe='')}",
                str(child_name),
                node,
            ))
        return node
    if prop_type == 9:
        value = payload["value"]
        return WzVectorProperty(name, int(value["x"]), int(value["y"]), parent)
    if prop_type == 8:
        return WzStringProperty(name, str(payload["value"]), parent)
    if prop_type == 4:
        return WzIntProperty(name, int(payload["value"]), parent)
    raise RuntimeError(f"unsupported TMS property type {prop_type}: {url}")


def carriers_match_specs() -> bool:
    for book, specs in SKINS_BY_BOOK.items():
        path = CLIENT_SKILL_DIR / f"{book}.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        root = image.parse()
        carrier = root.child(CARRIER_NAME)
        if image.truncated or image.parse_warnings or not isinstance(carrier, WzSubProperty):
            return False
        for spec in specs:
            node = carrier.child(str(spec.target_id))
            if (
                not isinstance(node, WzSubProperty)
                or int_value(node, "alignmentVersion", 0) != ALIGNMENT_VERSION
                or int_value(node, "sourceId", 0) != spec.source_id
            ):
                return False
    return True


def load_sources() -> dict[int, WzSubProperty]:
    if carriers_match_specs():
        print("TMS v209 source already pinned in client carriers")
        return {}
    sources = {}
    for spec in SKINS:
        node = WzSubProperty(str(spec.source_id))
        top_level = {"icon", "iconDisabled", "iconMouseOver"}
        top_level.update(path.split("/", 1)[0] for _, path in spec.visuals)
        for name in sorted(top_level):
            url = f"{TMS_API}/{spec.source_book}.img/skill/{spec.source_id}/{name}"
            node.add(tms_property(url, name, node))
        sources[spec.source_id] = node
        print(f"TMS v209 source: {spec.source_id} {spec.source_name}")
    return sources


def source_skill(sources: dict[int, WzSubProperty], spec: SkinSpec) -> WzSubProperty:
    node = sources.get(spec.source_id)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing Dual Blade skill: {spec.source_id}")
    return node


def copy_ems_tree(prop, name: str, parent, target_key: WzKey):
    if isinstance(prop, WzCanvasProperty):
        with decode_canvas(prop, region="GMS") as decoded:
            image = decoded.convert("RGBA")
        out = WzCanvasProperty(name, parent)
        out.width, out.height = image.size
        out.format = 1
        out.format2 = 0
        out._png_data = encode_canvas_payload(
            image, 1, out.width, out.height,
            key=target_key, listwz=False, zlib_level=9,
        )
        image.close()
        out._png_length = len(out._png_data)
        for child in prop.children():
            out.add(clone_property(child, child.name, out))
        return out
    if isinstance(prop, WzSubProperty):
        out = WzSubProperty(name, parent)
        for child in prop.children():
            out.add(copy_ems_tree(child, child.name, out, target_key))
        return out
    return clone_property(prop, name, parent)


def replace_child(parent: WzSubProperty, prop) -> None:
    prop.parent = parent
    parent._children[prop.name] = prop


def int_value(node: WzSubProperty, name: str, default: int | None = None) -> int | None:
    child = node.child(name)
    return int(child.value) if child is not None else default


def shift_canvas_origins(node, dx: int, dy: int) -> None:
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, WzCanvasProperty):
            origin = current.child("origin")
            if origin is not None:
                origin.x += dx
                origin.y += dy
        if hasattr(current, "children"):
            stack.extend(current.children())


def retime_direct_canvas_frames(node, duration: int) -> None:
    frames = [child for child in node.children() if isinstance(child, WzCanvasProperty)]
    if not frames:
        return
    old_delays = [int_value(frame, "delay", 100) for frame in frames]
    old_duration = sum(old_delays)
    if old_duration <= 0:
        raise RuntimeError(f"invalid animation duration: {node.name}")
    delays = [max(10, round(value * duration / old_duration)) for value in old_delays]
    difference = duration - sum(delays)
    index = 0
    while difference:
        step = 1 if difference > 0 else -1
        if step > 0 or delays[index] > 10:
            delays[index] += step
            difference -= step
        index = (index + 1) % len(delays)
    for frame, delay in zip(frames, delays):
        set_int(frame, "delay", delay)


def align_visual(node, spec: SkinSpec, branch_name: str) -> None:
    dx, dy = ORIGIN_OFFSETS.get((spec.target_id, branch_name), (0, 0))
    if dx or dy:
        shift_canvas_origins(node, dx, dy)
    if branch_name == "effect" and spec.target_id in EFFECT_DURATION_TARGETS:
        retime_direct_canvas_frames(node, EFFECT_DURATION_TARGETS[spec.target_id])


def fetch_icon_image(spec: SkinSpec, name: str) -> Image.Image:
    url = f"{ICON_API}/{spec.source_book}.img/skill/{spec.source_id}/{name}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "curl/8.7.1", "Accept": "application/json"},
    )
    payload = tms_api_json(url)
    png = base64.b64decode(payload["value"])
    with Image.open(io.BytesIO(png)) as decoded:
        return decoded.convert("RGBA")


def source_icon_image(source: WzSubProperty, name: str) -> Image.Image:
    icon = source.child(name)
    if not isinstance(icon, WzCanvasProperty):
        raise RuntimeError(f"missing TMS icon: {source.name}/{name}")
    with decode_canvas(icon, region="GMS") as decoded:
        return decoded.convert("RGBA")


def embedded_icon_hash(target: WzSubProperty) -> str | None:
    digest = hashlib.sha256()
    for name in ("icon", "iconDisabled", "iconMouseOver"):
        icon = target.child(name)
        if not isinstance(icon, WzCanvasProperty):
            return None
        digest.update(name.encode("ascii"))
        with decode_canvas(icon, region="GMS") as image:
            digest.update(image.convert("RGBA").tobytes())
    return digest.hexdigest()


def apply_icons(
    target: WzSubProperty,
    spec: SkinSpec,
    target_key: WzKey,
    source: WzSubProperty | None,
) -> None:
    if embedded_icon_hash(target) == ICON_PIXEL_HASHES[spec.source_id]:
        return
    fallback = target.child("icon")
    for name in ("icon", "iconDisabled", "iconMouseOver"):
        previous = target.child(name)
        metadata = previous if isinstance(previous, WzCanvasProperty) else fallback
        image = source_icon_image(source, name) if source is not None else fetch_icon_image(spec, name)
        icon = WzCanvasProperty(name, target)
        icon.width, icon.height = image.size
        icon.format = 1
        icon.format2 = 0
        icon._png_data = encode_canvas_payload(
            image, 1, icon.width, icon.height,
            key=target_key, listwz=False, zlib_level=9,
        )
        icon._png_length = len(icon._png_data)
        image.close()
        if isinstance(metadata, WzCanvasProperty):
            for child in metadata.children():
                icon.add(clone_property(child, child.name, icon))
        replace_child(target, icon)


def apply_legacy_attack_contract(
    target: WzSubProperty, baseline: WzSubProperty, spec: SkinSpec
) -> None:
    baseline_levels = baseline.child("level")
    if not isinstance(baseline_levels, WzSubProperty):
        raise RuntimeError(f"missing target skill levels: {spec.target_id}")
    replace_child(target, clone_property(baseline_levels, "level", target))
    set_int(target, "weapon", 33)
    target._children.pop("subWeapon", None)


def attack_parameter_hash(target: WzSubProperty, spec: SkinSpec) -> str:
    levels = target.child("level")
    payload = "|".join(
        f"{level.name}:{int_value(level, spec.damage_field)}:"
        f"{int_value(level, 'attackCount')}"
        for level in levels.children()
    )
    return sha256(payload.encode("ascii"))


def build_visual_carrier(
    root: WzSubProperty,
    specs: tuple[SkinSpec, ...],
    sources: dict[int, WzSubProperty],
    target_key: WzKey,
) -> WzSubProperty:
    previous = root.child(CARRIER_NAME)
    carrier = WzSubProperty(CARRIER_NAME, root)
    for spec in specs:
        target = root.get(f"skill/{spec.target_id}")
        if not isinstance(target, WzSubProperty):
            raise RuntimeError(f"missing target skill: {spec.target_id}")
        source = source_skill(sources, spec) if sources else None
        previous_target = (
            previous.child(str(spec.target_id))
            if isinstance(previous, WzSubProperty)
            else None
        )
        previously_aligned = (
            isinstance(previous_target, WzSubProperty)
            and int_value(previous_target, "alignmentVersion", 0) == ALIGNMENT_VERSION
        )
        target_carrier = WzSubProperty(str(spec.target_id), carrier)
        for target_name, source_path in spec.visuals:
            if source is not None:
                source_branch = source.get(source_path)
                if source_branch is None:
                    raise RuntimeError(
                        f"missing source visual: {spec.source_id}/{source_path}"
                    )
                replacement = copy_ems_tree(
                    source_branch, target_name, target_carrier, target_key
                )
            else:
                source_branch = (
                    previous_target.child(target_name)
                    if isinstance(previous_target, WzSubProperty)
                    else None
                )
                if source_branch is None:
                    raise RuntimeError(
                        f"missing pinned carrier visual: {spec.target_id}/{target_name}"
                    )
                replacement = clone_property(
                    source_branch, target_name, target_carrier
                )
            if source is not None or not previously_aligned:
                align_visual(replacement, spec, target_name)
            if target_name == "mob0" and isinstance(replacement, WzSubProperty):
                metadata_owner = target.child("mob0")
                if not isinstance(metadata_owner, WzSubProperty) and isinstance(
                    previous, WzSubProperty
                ):
                    metadata_owner = previous.get(f"{spec.target_id}/mob0")
                if isinstance(metadata_owner, WzSubProperty):
                    for name in ("pos", "repeat", "fixed"):
                        child = metadata_owner.child(name)
                        if child is not None:
                            replacement.add(clone_property(child, name, replacement))
            target_carrier.add(replacement)
        target_carrier.add(
            WzIntProperty("alignmentVersion", ALIGNMENT_VERSION, target_carrier)
        )
        target_carrier.add(WzIntProperty("sourceId", spec.source_id, target_carrier))
        carrier.add(target_carrier)
    return carrier


def uol_path_from_parent(parent, root_path: str) -> str:
    depth = 0
    current = parent
    while current.parent is not None:
        depth += 1
        current = current.parent
    return "../" * depth + root_path


def build_visual_proxy(source, name: str, parent, root_path: str):
    if isinstance(source, WzCanvasProperty):
        return WzUolProperty(name, uol_path_from_parent(parent, root_path), parent)
    if isinstance(source, WzSubProperty):
        proxy = WzSubProperty(name, parent)
        for child in source.children():
            proxy.add(
                build_visual_proxy(
                    child,
                    child.name,
                    proxy,
                    f"{root_path}/{child.name}",
                )
            )
        return proxy
    return clone_property(source, name, parent)


def apply_visual_proxies(
    target: WzSubProperty, carrier_skill: WzSubProperty, spec: SkinSpec
) -> None:
    for name in spec.remove_visuals:
        target._children.pop(name, None)
    for target_name, _ in spec.visuals:
        source = carrier_skill.child(target_name)
        if source is None:
            raise RuntimeError(f"missing carrier branch: {spec.target_id}/{target_name}")
        root_path = f"{CARRIER_NAME}/{spec.target_id}/{target_name}"
        replace_child(
            target,
            build_visual_proxy(source, target_name, target, root_path),
        )


def locate_skill_records(image: WzImage, data: bytes, path: Path):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {path}")
    reader.skip(2)
    root_count = reader.read_compressed_int()
    for _ in range(root_count):
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root property tag: {name}/{tag}")
        size_offset = reader.position
        block_size = reader.read_u32()
        block_start = reader.position
        block_end = block_start + block_size
        if name != "skill":
            reader.seek(block_end)
            continue
        if reader.read_string_block(0) != "Property":
            raise RuntimeError(f"invalid skill property block: {path}")
        reader.skip(2)
        count = reader.read_compressed_int()
        names = []
        spans = []
        for _ in range(count):
            start = reader.position
            child_name = reader.read_string_block(0)
            child_tag = reader.read_byte()
            if child_tag != 9:
                raise RuntimeError(f"unexpected skill record tag: {child_name}/{child_tag}")
            child_size = reader.read_u32()
            reader.seek(reader.position + child_size)
            names.append(child_name)
            spans.append((start, reader.position))
        if reader.position != block_end:
            raise RuntimeError(f"skill records do not fill their parent block: {path}")
        return size_offset, block_size, tuple(names), tuple(spans)
    raise RuntimeError(f"missing skill root: {path}")


def encode_record(node: WzSubProperty, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected encoded property-list prefix")
    return encoded[len(prefix):]


def encode_padded_record(
    node: WzSubProperty, image: WzImage, size: int, pad_target: str
) -> bytes:
    node._children.pop(PAD_NAME, None)
    if node.child(pad_target) is None:
        raise RuntimeError(f"missing padding target: {node.name}/{pad_target}")
    pad = WzUolProperty(PAD_NAME, pad_target, node)
    node.add(pad)
    encoded = bytearray(encode_record(node, image))
    if len(encoded) > size:
        raise RuntimeError(
            f"patched record exceeds its fixed span: {node.name}/{len(encoded)}>{size}"
        )

    pad_record = encode_record(pad, image)
    if not encoded.endswith(pad_record):
        raise RuntimeError(f"padding property is not final: {node.name}")
    trailing_size = size - len(encoded)
    pad_start = len(encoded) - len(pad_record)
    pad_size_offset = (
        pad_start + len(encode_string_block(image.wz_file.reader, PAD_NAME)) + 1
    )
    outer_size_offset = len(
        encode_string_block(image.wz_file.reader, node.name)
    ) + 1
    pad_size = struct.unpack_from("<I", encoded, pad_size_offset)[0]
    outer_size = struct.unpack_from("<I", encoded, outer_size_offset)[0]
    struct.pack_into("<I", encoded, pad_size_offset, pad_size + trailing_size)
    struct.pack_into("<I", encoded, outer_size_offset, outer_size + trailing_size)
    encoded.extend(b"\x00" * trailing_size)
    return bytes(encoded)


def locate_root_records(image: WzImage, data: bytes, path: Path):
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {path}")
    reader.skip(2)
    count_offset = reader.position
    count = reader.read_compressed_int()
    count_size = reader.position - count_offset
    names = []
    spans = []
    for _ in range(count):
        start = reader.position
        name = reader.read_string_block(0)
        tag = reader.read_byte()
        if tag != 9:
            raise RuntimeError(f"unexpected root property tag: {path}/{name}/{tag}")
        block_size = reader.read_u32()
        reader.seek(reader.position + block_size)
        names.append(name)
        spans.append((start, reader.position))
    if reader.position != len(data):
        raise RuntimeError(f"root records do not fill the IMG: {path}")
    return count_offset, count_size, tuple(names), tuple(spans)


def git_blob(revision: str, relative_path: str) -> bytes:
    return subprocess.run(
        ["git", "cat-file", "blob", f"{revision}:{relative_path}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout


def restore_legacy_auxiliary_skill_records(data: bytes, path: Path) -> bytes:
    relative = str(path.relative_to(ROOT))
    baseline = git_blob(LEGACY_BASELINE, relative)
    current_image = WzImage.from_bytes(data, key=WzKey.for_region("GMS"), name=path.name)
    baseline_image = WzImage.from_bytes(
        baseline, key=WzKey.for_region("GMS"), name=path.name
    )
    current_image.parse()
    baseline_image.parse()
    _, _, current_names, current_spans = locate_skill_records(
        current_image, data, path
    )
    _, _, baseline_names, baseline_spans = locate_skill_records(
        baseline_image, baseline, path
    )
    result = bytearray(data)
    for skill_id in LEGACY_AUXILIARY_SKILLS:
        name = str(skill_id)
        current_start, current_end = current_spans[current_names.index(name)]
        baseline_start, baseline_end = baseline_spans[baseline_names.index(name)]
        record = baseline[baseline_start:baseline_end]
        if len(record) != current_end - current_start:
            raise RuntimeError(f"legacy auxiliary span changed: {skill_id}")
        result[current_start:current_end] = record
    return bytes(result)


def restore_legacy_auxiliary_string_records(data: bytes) -> bytes:
    relative = str(CLIENT_STRING.relative_to(ROOT))
    baseline = git_blob(LEGACY_BASELINE, relative)
    current_image = WzImage.from_bytes(
        data, key=WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    baseline_image = WzImage.from_bytes(
        baseline, key=WzKey.for_region("GMS"), name=CLIENT_STRING.name
    )
    current_image.parse()
    baseline_image.parse()
    _, _, current_names, current_spans = locate_root_records(
        current_image, data, CLIENT_STRING
    )
    _, _, baseline_names, baseline_spans = locate_root_records(
        baseline_image, baseline, CLIENT_STRING
    )
    result = bytearray(data)
    for skill_id in LEGACY_AUXILIARY_SKILLS:
        name = str(skill_id)
        current_start, current_end = current_spans[current_names.index(name)]
        baseline_start, baseline_end = baseline_spans[baseline_names.index(name)]
        record = baseline[baseline_start:baseline_end]
        if len(record) != current_end - current_start:
            raise RuntimeError(f"legacy auxiliary string span changed: {skill_id}")
        result[current_start:current_end] = record
    return bytes(result)


def append_or_replace_carrier(
    data: bytes, image: WzImage, carrier: WzSubProperty, path: Path
) -> bytes:
    count_offset, count_size, names, spans = locate_root_records(image, data, path)
    encoded = encode_record(carrier, image)
    if CARRIER_NAME in names:
        index = names.index(CARRIER_NAME)
        if index != len(names) - 1:
            raise RuntimeError(f"{CARRIER_NAME} must remain the final root record: {path}")
        start, end = spans[index]
        return data[:start] + encoded + data[end:]

    new_count = encode_compressed_int(len(names) + 1)
    if len(new_count) != count_size:
        raise RuntimeError(f"root count width changed: {path}")
    updated = bytearray(data)
    updated[count_offset:count_offset + count_size] = new_count
    updated.extend(encoded)
    return bytes(updated)


def patch_client_skill_book(
    book: int,
    specs: tuple[SkinSpec, ...],
    sources: dict[int, WzSubProperty],
    dry_run: bool,
) -> bytes:
    path = CLIENT_SKILL_DIR / f"{book}.img"
    original = path.read_bytes()
    if book == 420:
        original = restore_legacy_auxiliary_skill_records(original, path)
    image = WzImage.from_bytes(original, key=WzKey.for_region("GMS"), name=path.name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {path}: {image.parse_warnings}")
    skill_root = root.child("skill")
    if not isinstance(skill_root, WzSubProperty):
        raise RuntimeError(f"missing client skill root: {path}")
    size_offset, old_size, names, spans = locate_skill_records(image, original, path)
    raw_records = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    baseline_data = git_blob(LEGACY_BASELINE, str(path.relative_to(ROOT)))
    baseline_image = WzImage.from_bytes(
        baseline_data, key=WzKey.for_region("GMS"), name=f"baseline-{path.name}"
    )
    baseline_root = baseline_image.parse()
    if baseline_image.truncated or baseline_image.parse_warnings:
        raise RuntimeError(
            f"cannot use malformed baseline {path}: {baseline_image.parse_warnings}"
        )
    carrier = build_visual_carrier(root, specs, sources, image.wz_file.reader.key)
    replacements = {}
    for spec in specs:
        target = skill_root.child(str(spec.target_id))
        if not isinstance(target, WzSubProperty):
            raise RuntimeError(f"missing target skill: {spec.target_id}")
        carrier_skill = carrier.child(str(spec.target_id))
        apply_visual_proxies(target, carrier_skill, spec)
        source = source_skill(sources, spec) if sources else None
        apply_icons(target, spec, image.wz_file.reader.key, source)
        baseline = baseline_root.get(f"skill/{spec.target_id}")
        if not isinstance(baseline, WzSubProperty):
            raise RuntimeError(f"missing baseline skill: {spec.target_id}")
        if spec.is_attack:
            apply_legacy_attack_contract(target, baseline, spec)
        replacements[str(spec.target_id)] = encode_padded_record(
            target, image, len(raw_records[str(spec.target_id)]), "level"
        )
    rebuilt = b"".join(replacements.get(name, raw_records[name]) for name in names)
    records_start, records_end = spans[0][0], spans[-1][1]
    updated = original[:records_start] + rebuilt + original[records_end:]
    if len(updated) != len(original):
        raise RuntimeError(f"skill record spans shifted: {path}")
    if struct.unpack_from("<I", updated, size_offset)[0] != old_size:
        raise RuntimeError(f"skill parent size changed: {path}")
    for name, record in raw_records.items():
        if name not in replacements and record not in updated:
            raise RuntimeError(f"unapproved client skill record changed: {book}/{name}")
    result = append_or_replace_carrier(updated, image, carrier, path)
    if not dry_run:
        atomic_write_bytes(path, result)
    print(f"client {book}.img: changed={len(replacements)} preserved={len(names) - len(replacements)}")
    return result


def level_text(spec: SkinSpec, level: WzSubProperty) -> str:
    mp = int_value(level, "mpCon", 0)
    damage = int_value(level, spec.damage_field, 0)
    count = int_value(level, "attackCount", 1)
    mobs = int_value(level, "mobCount", 1)
    if spec.target_id == 4211006:
        return f"消耗MP {mp}，以{damage}%伤害引爆1枚金币"
    if spec.target_id == 4221001:
        critical = int_value(level, "criticalDamage", 0)
        prop = int_value(level, "prop", 0)
        return (
            f"消耗MP {mp}，以{damage}%伤害攻击{count}次，"
            f"必杀伤害{critical}%，触发几率{prop}%"
        )
    if spec.target_id == 4221003:
        effect = int_value(level, "x", 0)
        return (
            f"消耗MP {mp}，最多攻击{mobs}名敌人，以{damage}%伤害攻击{count}次，"
            f"挑衅效果{effect}%"
        )
    if spec.target_id == 4221004:
        duration = int_value(level, "time", 0)
        return (
            f"消耗MP {mp}，最多攻击{mobs}名敌人，每次以{damage}%伤害攻击{count}次，"
            f"持续{duration}秒"
        )
    if spec.target_id in (4211002, 4221007):
        prop = int_value(level, "prop", 0)
        return (
            f"消耗MP {mp}，最多攻击{mobs}名敌人，以{damage}%伤害攻击{count}次，"
            f"{prop}%几率使敌人昏迷"
        )
    if spec.target_id == 4211004:
        return f"消耗MP {mp}，最多攻击{mobs}名敌人，以{damage}%伤害攻击{count}次"
    return f"消耗MP {mp}，以{damage}%伤害攻击{count}次"


def build_descriptions(
    skill_roots: dict[int, WzSubProperty],
) -> dict[int, tuple[str, str, dict[str, str]]]:
    result = {}
    for spec in SKINS:
        target = skill_roots[spec.target_id]
        texts = {}
        if spec.is_attack:
            levels = target.child("level")
            texts = {
                f"h{level.name}": level_text(spec, level)
                for level in levels.children()
            }
        result[spec.target_id] = (spec.source_name, spec.description, texts)
    return result


def resolve_uol(node):
    seen = set()
    while isinstance(node, WzUolProperty):
        if id(node) in seen or node.parent is None:
            return None
        seen.add(id(node))
        node = node.parent.get(node.value)
    return node


def patch_client_string(
    descriptions: dict[int, tuple[str, str, dict[str, str]]], dry_run: bool
) -> bytes:
    original = CLIENT_STRING.read_bytes()
    original = restore_legacy_auxiliary_string_records(original)
    image = WzImage.from_bytes(original, key=WzKey.for_region("GMS"), name=CLIENT_STRING.name)
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"cannot patch malformed {CLIENT_STRING}: {image.parse_warnings}")
    _, _, names, spans = locate_root_records(image, original, CLIENT_STRING)
    raw_records = {name: original[start:end] for name, (start, end) in zip(names, spans)}
    replacements = {}
    for skill_id, (skill_name, description, texts) in descriptions.items():
        node = root.child(str(skill_id))
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing client skill string: {skill_id}")
        set_string(node, "name", skill_name)
        set_string(node, "desc", description)
        for name, value in texts.items():
            set_string(node, name, value)
        replacements[str(skill_id)] = encode_padded_record(
            node, image, len(raw_records[str(skill_id)]), "name"
        )
    rebuilt = b"".join(replacements.get(name, raw_records[name]) for name in names)
    records_start, records_end = spans[0][0], spans[-1][1]
    result = original[:records_start] + rebuilt + original[records_end:]
    if len(result) != len(original):
        raise RuntimeError("String/Skill.img record spans shifted")
    for name, record in raw_records.items():
        if name not in replacements and record not in result:
            raise RuntimeError(f"unapproved client string record changed: {name}")
    if not dry_run:
        atomic_write_bytes(CLIENT_STRING, result)
    print(f"client String/Skill.img: changed={len(replacements)} preserved={len(names) - len(replacements)}")
    return result


def patch_client_consume_string(dry_run: bool) -> bytes:
    original = CLIENT_CONSUME_STRING.read_bytes()
    image = WzImage.from_bytes(
        original, key=WzKey.for_region("GMS"), name=CLIENT_CONSUME_STRING.name
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"cannot patch malformed {CLIENT_CONSUME_STRING}: {image.parse_warnings}"
        )
    _, _, names, spans = locate_root_records(
        image, original, CLIENT_CONSUME_STRING
    )
    raw_records = {
        name: original[start:end] for name, (start, end) in zip(names, spans)
    }
    replacements = {}
    for item_id, (item_name, description) in CONSUME_STRINGS.items():
        record_name = str(item_id)
        node = root.child(record_name)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing client consume string: {item_id}")
        set_string(node, "name", item_name)
        set_string(node, "desc", description)
        replacements[record_name] = encode_padded_record(
            node, image, len(raw_records[record_name]), "name"
        )
    rebuilt = b"".join(replacements.get(name, raw_records[name]) for name in names)
    records_start, records_end = spans[0][0], spans[-1][1]
    result = original[:records_start] + rebuilt + original[records_end:]
    if len(result) != len(original):
        raise RuntimeError("String/Consume.img record spans shifted")
    if not dry_run:
        atomic_write_bytes(CLIENT_CONSUME_STRING, result)
    print(
        "client String/Consume.img: "
        f"changed={len(replacements)} preserved={len(names) - len(replacements)}"
    )
    return result


def xml_set_int(parent: ET.Element, name: str, value: int) -> None:
    child = next((item for item in parent if item.get("name") == name), None)
    if child is None:
        child = ET.SubElement(parent, "int", {"name": name, "value": str(value)})
    else:
        child.tag = "int"
        child.set("value", str(value))


def xml_replace_child(parent: ET.Element, name: str, replacement: ET.Element) -> None:
    for index, child in enumerate(parent):
        if child.get("name") == name:
            parent.remove(child)
            parent.insert(index, replacement)
            return
    raise RuntimeError(f"missing XML child: {parent.get('name')}/{name}")


def replace_xml_blocks(text: str, replacements: dict[int, ET.Element]) -> str:
    spans = []
    for skill_id, node in replacements.items():
        start, end = find_imgdir_block(text, str(skill_id))
        spans.append((start, end, ET.tostring(node, encoding="unicode", short_empty_elements=True)))
    for start, end, replacement in sorted(spans, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def patch_server_skills(
    client_skills: dict[int, WzSubProperty], dry_run: bool
) -> None:
    for book in (420, 421, 422):
        specs = tuple(spec for spec in ATTACK_SPECS if spec.target_id // 10000 == book)
        path = SERVER_SKILL_DIR / f"{book}.img.xml"
        text = path.read_text(encoding="utf-8")
        baseline_text = git_blob(
            LEGACY_BASELINE, str(path.relative_to(ROOT))
        ).decode("utf-8")
        replacements = {}
        for spec in specs:
            start, end = find_imgdir_block(text, str(spec.target_id))
            block = ET.fromstring(text[start:end])
            baseline_start, baseline_end = find_imgdir_block(
                baseline_text, str(spec.target_id)
            )
            baseline_block = ET.fromstring(
                baseline_text[baseline_start:baseline_end]
            )
            baseline_levels = baseline_block.find("./imgdir[@name='level']")
            if baseline_levels is None:
                raise RuntimeError(f"missing baseline server levels: {spec.target_id}")
            xml_replace_child(block, "level", baseline_levels)
            for child in tuple(block):
                if child.get("name") == "subWeapon":
                    block.remove(child)
            xml_set_int(block, "weapon", 33)
            replacements[spec.target_id] = block
        updated = replace_xml_blocks(text, replacements)
        if not dry_run:
            atomic_write_text(path, updated)
        print(f"server {book}.img.xml: changed={len(replacements)}")


def patch_server_skill_string(
    path: Path,
    descriptions: dict[int, tuple[str, str, dict[str, str]]],
    dry_run: bool,
) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {}
    for skill_id, (skill_name, description, texts) in descriptions.items():
        start, end = find_imgdir_block(text, str(skill_id))
        block = ET.fromstring(text[start:end])
        name_node = next((item for item in block if item.get("name") == "name"), None)
        if name_node is None:
            name_node = ET.SubElement(block, "string", {"name": "name"})
        name_node.set("value", skill_name)
        desc = next((item for item in block if item.get("name") == "desc"), None)
        if desc is None:
            desc = ET.SubElement(block, "string", {"name": "desc"})
        desc.set("value", description)
        for name, value in texts.items():
            child = next((item for item in block if item.get("name") == name), None)
            if child is None:
                child = ET.SubElement(block, "string", {"name": name})
            child.set("value", value)
        replacements[skill_id] = block
    updated = replace_xml_blocks(text, replacements)
    if not dry_run:
        atomic_write_text(path, updated)
    print(f"server {path.parent.parent.name}/Skill.img.xml: changed={len(replacements)}")


def restore_server_auxiliary_skill_strings(path: Path, dry_run: bool) -> None:
    relative = str(path.relative_to(ROOT))
    baseline = git_blob(LEGACY_BASELINE, relative).decode("utf-8")
    current = path.read_text(encoding="utf-8")
    for skill_id in LEGACY_AUXILIARY_SKILLS:
        baseline_start, baseline_end = find_imgdir_block(baseline, str(skill_id))
        current_start, current_end = find_imgdir_block(current, str(skill_id))
        current = (
            current[:current_start]
            + baseline[baseline_start:baseline_end]
            + current[current_end:]
        )
    if not dry_run:
        atomic_write_text(path, current)
    print(f"server {path.parent.parent.name}/Skill.img.xml: restored=2")


def patch_server_consume_string(path: Path, dry_run: bool) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {}
    for item_id, (item_name, description) in CONSUME_STRINGS.items():
        start, end = find_imgdir_block(text, str(item_id))
        block = ET.fromstring(text[start:end])
        values = {child.get("name"): child for child in block}
        values["name"].set("value", item_name)
        values["desc"].set("value", description)
        replacements[item_id] = block
    updated = replace_xml_blocks(text, replacements)
    if not dry_run:
        atomic_write_text(path, updated)
    print(f"server {path.parent.parent.name}/Consume.img.xml: changed={len(replacements)}")


def validate_outputs() -> None:
    for book, specs in SKINS_BY_BOOK.items():
        path = CLIENT_SKILL_DIR / f"{book}.img"
        image = WzImage.from_bytes(path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name)
        root = image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"invalid patched client IMG: {path}/{image.parse_warnings}")
        baseline_data = git_blob(
            LEGACY_BASELINE, f"clien/Data/Skill/{book}.img"
        )
        baseline_image = WzImage.from_bytes(
            baseline_data, key=WzKey.for_region("GMS"), name=f"baseline-{book}.img"
        )
        baseline_root = baseline_image.parse()
        for spec in specs:
            node = root.get(f"skill/{spec.target_id}")
            if spec.is_attack and spec.target_id in LEGACY_ATTACK_PARAMETER_HASHES:
                if attack_parameter_hash(node, spec) != LEGACY_ATTACK_PARAMETER_HASHES[spec.target_id]:
                    raise RuntimeError(f"attack parameters drifted: {spec.target_id}")
                if int_value(node, "weapon") != 33 or node.child("subWeapon") is not None:
                    raise RuntimeError(f"skill is not dagger-only: {spec.target_id}")
                actual_levels = node.child("level")
                baseline_levels = baseline_root.get(
                    f"skill/{spec.target_id}/level"
                )
                actual_signature = tuple(
                    (
                        level.name,
                        tuple((child.name, child.value) for child in level.children()),
                    )
                    for level in actual_levels.children()
                )
                baseline_signature = tuple(
                    (
                        level.name,
                        tuple((child.name, child.value) for child in level.children()),
                    )
                    for level in baseline_levels.children()
                )
                if actual_signature != baseline_signature:
                    raise RuntimeError(f"legacy level contract drifted: {spec.target_id}")
            pad = node.child(PAD_NAME)
            if not isinstance(pad, WzUolProperty) or resolve_uol(pad) is None:
                raise RuntimeError(f"invalid non-cyclic skill padding: {spec.target_id}")
            for icon_name in ("icon", "iconDisabled", "iconMouseOver"):
                icon = node.child(icon_name)
                if not isinstance(icon, WzCanvasProperty):
                    raise RuntimeError(f"missing Dual Blade icon: {spec.target_id}/{icon_name}")
                if (int(icon.format), int(icon.format2)) != (1, 0):
                    raise RuntimeError(f"non-ARGB4444 icon: {spec.target_id}/{icon_name}")
                with decode_canvas(icon, region="GMS") as decoded:
                    if decoded.getchannel("A").getbbox() is None:
                        raise RuntimeError(f"blank Dual Blade icon: {spec.target_id}/{icon_name}")
            for target_name, _ in spec.visuals:
                branch = node.child(target_name)
                if not isinstance(branch, WzSubProperty):
                    raise RuntimeError(f"missing patched visual: {spec.target_id}/{target_name}")
                stack = [branch]
                visible = False
                while stack:
                    current = stack.pop()
                    if isinstance(current, WzUolProperty):
                        current = resolve_uol(current)
                        if current is None:
                            raise RuntimeError(
                                f"unresolved visual frame: {spec.target_id}/{target_name}"
                            )
                    if isinstance(current, WzCanvasProperty):
                        if (int(current.format), int(current.format2)) != (1, 0):
                            raise RuntimeError(f"non-ARGB4444 Canvas: {spec.target_id}/{target_name}")
                        with decode_canvas(current, region="GMS") as decoded:
                            visible = visible or decoded.getchannel("A").getbbox() is not None
                    if hasattr(current, "children"):
                        stack.extend(current.children())
                if not visible:
                    raise RuntimeError(f"blank patched visual: {spec.target_id}/{target_name}")
    ET.parse(SERVER_SKILL_DIR / "420.img.xml")
    ET.parse(SERVER_SKILL_DIR / "421.img.xml")
    ET.parse(SERVER_SKILL_DIR / "422.img.xml")
    for path in (*SERVER_SKILL_STRINGS, *SERVER_CONSUME_STRINGS):
        ET.parse(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--allow-retired-experiment",
        action="store_true",
        help="explicitly run the retired lower-job experiment",
    )
    args = parser.parse_args()
    if not args.allow_retired_experiment:
        raise SystemExit(
            "retired: Shadower jobs 1-4 must remain at the legacy baseline; "
            "use patch_explorer_other_v_vi.py --job shadower"
        )

    sources = load_sources()
    patched_roots = {}
    for book, specs in SKINS_BY_BOOK.items():
        result = patch_client_skill_book(book, specs, sources, args.dry_run)
        image = WzImage.from_bytes(result, key=WzKey.for_region("GMS"), name=f"{book}.img")
        root = image.parse()
        for spec in specs:
            patched_roots[spec.target_id] = root.get(f"skill/{spec.target_id}")
    descriptions = build_descriptions(patched_roots)
    patch_client_string(descriptions, args.dry_run)
    patch_client_consume_string(args.dry_run)
    patch_server_skills(patched_roots, args.dry_run)
    for path in SERVER_SKILL_STRINGS:
        patch_server_skill_string(path, descriptions, args.dry_run)
        restore_server_auxiliary_skill_strings(path, args.dry_run)
    for path in SERVER_CONSUME_STRINGS:
        patch_server_consume_string(path, args.dry_run)
    if not args.dry_run:
        validate_outputs()


if __name__ == "__main__":
    main()
