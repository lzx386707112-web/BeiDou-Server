#!/usr/bin/env python3
"""Build legacy-safe TMS damage-skin previews and WZ glyph groups."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import WzCanvasProperty, WzImage, WzKey, WzSubProperty  # noqa: E402
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.properties import WzIntProperty, WzStringProperty, WzVectorProperty  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
SOURCE_META = TMS_DATA / "Etc/DamageSkin.img"
SOURCE_CANVAS = TMS_DATA / "Etc/_Canvas/DamageSkin.img"
SOURCE_STRINGS = TMS_DATA / "String/Consume.img"
CLIENT_BASIC = ROOT / "clien/Data/Effect/BasicEff.img"
CLIENT_PREVIEWS = ROOT / "clien/Data/Effect/DamageSkin.img"
CLIENT_SKINS = ROOT / "clien/Data/Effect/DamageSkin"
SERVER_CATALOG = ROOT / "gms-server/src/main/java/org/gms/server/DamageSkinCatalog.java"
MANIFEST = ROOT / "docs/migrations/damage-skin-catalog.json"

BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
GROUPS = ("NoRed0", "NoRed1", "NoCri0", "NoCri1")
DIGITS = tuple(str(value) for value in range(10))
REQUIRED_EXTRAS = {
    "NoRed0": ("Miss",),
    "NoCri1": ("effect",),
}
PREVIEW_SIZE = (160, 60)


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"unsafe IMG parse for {path}: {image.parse_warnings}")
    return image


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def encode_root(root: WzSubProperty, template: WzImage) -> bytes:
    image = WzImage(
        name=root.name,
        parent=None,
        offset=0,
        size=0,
        wz_file=template.wz_file,
    )
    image._root = root
    image._parsed = True
    return encode_image_body(image, gms_reader())


def linked_canvas(node, payload: WzImage) -> WzCanvasProperty:
    current = node
    while isinstance(current, WzSubProperty) and not isinstance(current, WzCanvasProperty):
        current = current.child("0")
    if not isinstance(current, WzCanvasProperty):
        raise RuntimeError("digit has no Canvas frame 0")
    outlink = current.child("_outlink")
    if not isinstance(outlink, WzStringProperty):
        raise RuntimeError("digit Canvas has no _outlink")
    prefix = "Etc/_Canvas/DamageSkin.img/"
    value = str(outlink.value).replace("\\", "/")
    if not value.startswith(prefix):
        raise RuntimeError(f"unsupported damage-skin outlink: {value}")
    resolved = payload.root.get(value[len(prefix) :])
    if not isinstance(resolved, WzCanvasProperty) or not resolved.has_pixels():
        raise RuntimeError(f"unresolved damage-skin outlink: {value}")
    return resolved


def fit_to_size(source: Image.Image, size: tuple[int, int]) -> Image.Image:
    source = source.convert("RGBA")
    if source.width <= 0 or source.height <= 0:
        raise RuntimeError("cannot resize an empty Canvas")
    scale = min(size[0] / source.width, size[1] / source.height)
    scaled_size = (
        max(1, min(size[0], round(source.width * scale))),
        max(1, min(size[1], round(source.height * scale))),
    )
    resized = source.resize(scaled_size, Image.Resampling.LANCZOS)
    output = Image.new("RGBA", size)
    output.alpha_composite(
        resized,
        ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2),
    )
    return output


def resolve_sample(meta_skin: WzSubProperty, payload: WzImage, digit_images: list[Image.Image]) -> Image.Image:
    sample = meta_skin.child("sample")
    if sample is not None:
        try:
            return decode_canvas(linked_canvas(sample, payload), region="BMS").convert("RGBA")
        except RuntimeError:
            pass
    width = sum(image.width for image in digit_images)
    height = max(image.height for image in digit_images)
    composed = Image.new("RGBA", (width, height))
    x = 0
    for image in digit_images:
        composed.alpha_composite(image, (x, height - image.height))
        x += image.width
    return composed


def canvas_property(
    name: str,
    parent: WzSubProperty,
    pixels: Image.Image,
    origin: tuple[int, int] | None = None,
) -> WzCanvasProperty:
    canvas = WzCanvasProperty(name, parent)
    canvas.width, canvas.height = pixels.size
    canvas.format, canvas.format2 = 1, 0
    canvas._png_data = encode_canvas_payload(
        pixels, 1, pixels.width, pixels.height, key=GMS_KEY, listwz=False, zlib_level=9
    )
    canvas._png_length = len(canvas._png_data)
    if origin is not None:
        canvas.add(WzVectorProperty("origin", origin[0], origin[1], canvas))
    return canvas


def item_name(meta_skin: WzSubProperty, strings: WzImage, skin_id: int) -> str:
    extract_id = meta_skin.child("extractID")
    if isinstance(extract_id, WzIntProperty):
        name = strings.root.get(f"{int(extract_id.value)}/name")
        if isinstance(name, WzStringProperty) and str(name.value).strip():
            return str(name.value).strip()
    return f"伤害皮肤 {skin_id}"


def java_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def build_catalog_java(catalog: list[dict]) -> bytes:
    ids = ", ".join(str(entry["id"]) for entry in catalog)
    names = ",\n".join(f'        "{java_string(entry["name"])}"' for entry in catalog)
    source = f"""package org.gms.server;

/** Generated by migrate_damage_skins.py from the TMS damage-skin catalog. */
public final class DamageSkinCatalog {{
    private static final int[] IDS = {{{ids}}};
    private static final String[] NAMES = {{
{names}
    }};

    private DamageSkinCatalog() {{}}

    public static int[] ids() {{
        return IDS.clone();
    }}

    public static boolean contains(int skinId) {{
        return indexOf(skinId) >= 0;
    }}

    public static String nameOf(int skinId) {{
        int index = indexOf(skinId);
        return index >= 0 ? NAMES[index] : "未知伤害皮肤";
    }}

    private static int indexOf(int skinId) {{
        int low = 0;
        int high = IDS.length - 1;
        while (low <= high) {{
            int middle = (low + high) >>> 1;
            int candidate = IDS[middle];
            if (candidate < skinId) {{
                low = middle + 1;
            }} else if (candidate > skinId) {{
                high = middle - 1;
            }} else {{
                return middle;
            }}
        }}
        return -1;
    }}
}}
"""
    return source.encode("utf-8")


def build_outputs() -> tuple[dict[Path, bytes], dict]:
    metadata = load_image(SOURCE_META, BMS_KEY)
    payload = load_image(SOURCE_CANVAS, BMS_KEY)
    strings = load_image(SOURCE_STRINGS, BMS_KEY)
    basic = load_image(CLIENT_BASIC, GMS_KEY)

    glyph_sizes = {}
    glyph_origins = {}
    legacy_extras = {}
    for group in GROUPS:
        for digit in DIGITS:
            canvas = basic.root.get(f"{group}/{digit}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"legacy glyph missing: {group}/{digit}")
            glyph_sizes[(group, digit)] = (int(canvas.width), int(canvas.height))
            origin = canvas.child("origin")
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"legacy glyph origin missing: {group}/{digit}")
            glyph_origins[(group, digit)] = (int(origin.x), int(origin.y))
        for name in REQUIRED_EXTRAS.get(group, ()):
            canvas = basic.root.get(f"{group}/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"legacy damage node missing: {group}/{name}")
            origin = canvas.child("origin")
            if not isinstance(origin, WzVectorProperty):
                raise RuntimeError(f"legacy damage node origin missing: {group}/{name}")
            legacy_extras[(group, name)] = (
                decode_canvas(canvas, region="GMS").convert("RGBA"),
                (int(origin.x), int(origin.y)),
            )

    preview_root = WzSubProperty("DamageSkin.img")
    preview_dir = WzSubProperty("preview", preview_root)
    preview_root.add(preview_dir)
    catalog = []
    skipped = []
    skin_outputs: dict[Path, bytes] = {}

    numeric_skins = sorted(
        (node for node in metadata.root.children() if node.name.isdigit()),
        key=lambda node: int(node.name),
    )
    for meta_skin in numeric_skins:
        skin_id = int(meta_skin.name)
        red_zero_images: list[Image.Image] = []
        projected_groups: dict[str, list[Image.Image]] = {}
        try:
            for group in GROUPS:
                projected_digits = []
                for digit in DIGITS:
                    source = linked_canvas(meta_skin.get(f"effect/{group}/{digit}"), payload)
                    decoded = decode_canvas(source, region="BMS").convert("RGBA")
                    normalized = fit_to_size(decoded, glyph_sizes[(group, digit)])
                    projected_digits.append(normalized)
                    if group == "NoRed0":
                        red_zero_images.append(decoded)
                projected_groups[group] = projected_digits
            preview = fit_to_size(resolve_sample(meta_skin, payload, red_zero_images), PREVIEW_SIZE)
        except Exception as error:
            skipped.append({"id": skin_id, "reason": str(error)})
            continue

        preview_dir.add(canvas_property(str(skin_id), preview_dir, preview))
        skin = WzSubProperty(f"{skin_id}.img")
        for group in GROUPS:
            group_dir = WzSubProperty(group, skin)
            skin.add(group_dir)
            for digit, pixels in zip(DIGITS, projected_groups[group]):
                group_dir.add(
                    canvas_property(
                        digit,
                        group_dir,
                        pixels,
                        origin=glyph_origins[(group, digit)],
                    )
                )
            for name in REQUIRED_EXTRAS.get(group, ()):
                pixels, origin = legacy_extras[(group, name)]
                group_dir.add(canvas_property(name, group_dir, pixels, origin=origin))
        skin_outputs[CLIENT_SKINS / f"{skin_id}.img"] = encode_root(skin, metadata)
        catalog.append({"id": skin_id, "name": item_name(meta_skin, strings, skin_id)})

    if not catalog or catalog[0]["id"] != 0:
        raise RuntimeError("the default skin ID 0 must be present")

    preview_bytes = encode_root(preview_root, metadata)
    manifest = {
        "source": str(SOURCE_META),
        "catalogCount": len(catalog),
        "skippedCount": len(skipped),
        "glyphsPerSkin": len(GROUPS) * len(DIGITS),
        "runtimeCanvasesPerSkin": len(GROUPS) * len(DIGITS)
        + sum(len(names) for names in REQUIRED_EXTRAS.values()),
        "previewSize": list(PREVIEW_SIZE),
        "projection": "animated digits use frame 0; glyphs are centered and scaled to v83 BasicEff dimensions",
        "resourceLayout": "Effect/DamageSkin/<id>.img/<group>/<digit>",
        "catalog": catalog,
        "skipped": skipped,
    }
    outputs = {
        CLIENT_PREVIEWS: preview_bytes,
        SERVER_CATALOG: build_catalog_java(catalog),
        MANIFEST: (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    }
    outputs.update(skin_outputs)
    return outputs, manifest


def verify_outputs(outputs: dict[Path, bytes], manifest: dict) -> None:
    preview = WzImage.from_bytes(outputs[CLIENT_PREVIEWS], key=GMS_KEY, name="DamageSkin.img")
    preview.parse()
    if preview.truncated or preview.parse_warnings:
        raise RuntimeError(f"generated preview parse failed: {preview.parse_warnings}")
    basic = load_image(CLIENT_BASIC, GMS_KEY)
    legacy_extra_pixels = {}
    for group, names in REQUIRED_EXTRAS.items():
        for name in names:
            canvas = basic.root.get(f"{group}/{name}")
            if not isinstance(canvas, WzCanvasProperty):
                raise RuntimeError(f"legacy damage node missing during verification: {group}/{name}")
            legacy_extra_pixels[(group, name)] = decode_canvas(canvas, region="GMS").convert("RGBA").tobytes()
    ids = [entry["id"] for entry in manifest["catalog"]]
    if len(ids) != len(set(ids)) or ids != sorted(ids):
        raise RuntimeError("catalog IDs must be unique and sorted")
    for skin_id in ids:
        canvas = preview.root.get(f"preview/{skin_id}")
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing preview Canvas for skin {skin_id}")
        if (int(canvas.format), int(canvas.format2)) != (1, 0):
            raise RuntimeError(f"non-ARGB4444 preview for skin {skin_id}")
        pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
        if pixels.getbbox() is None:
            raise RuntimeError(f"transparent preview for skin {skin_id}")
        skin_path = CLIENT_SKINS / f"{skin_id}.img"
        skin = WzImage.from_bytes(outputs[skin_path], key=GMS_KEY, name=skin_path.name)
        skin.parse()
        if skin.truncated or skin.parse_warnings:
            raise RuntimeError(f"generated skin IMG parse failed {skin_id}: {skin.parse_warnings}")
        for group in GROUPS:
            group_node = skin.root.get(group)
            expected_names = DIGITS + REQUIRED_EXTRAS.get(group, ())
            if not isinstance(group_node, WzSubProperty) or tuple(
                child.name for child in group_node.children()
            ) != expected_names:
                raise RuntimeError(f"legacy group layout mismatch {skin_id}/{group}")
            for digit in DIGITS:
                glyph = skin.root.get(f"{group}/{digit}")
                if not isinstance(glyph, WzCanvasProperty):
                    raise RuntimeError(f"missing WZ glyph {skin_id}/{group}/{digit}")
                if (int(glyph.format), int(glyph.format2)) != (1, 0):
                    raise RuntimeError(f"non-ARGB4444 WZ glyph {skin_id}/{group}/{digit}")
                legacy = basic.root.get(f"{group}/{digit}")
                if not isinstance(legacy, WzCanvasProperty):
                    raise RuntimeError(f"legacy glyph missing during verification: {group}/{digit}")
                if (int(glyph.width), int(glyph.height)) != (int(legacy.width), int(legacy.height)):
                    raise RuntimeError(f"WZ glyph size mismatch {skin_id}/{group}/{digit}")
                glyph_origin = glyph.child("origin")
                legacy_origin = legacy.child("origin")
                if not isinstance(glyph_origin, WzVectorProperty) or not isinstance(legacy_origin, WzVectorProperty):
                    raise RuntimeError(f"WZ glyph origin missing {skin_id}/{group}/{digit}")
                if (int(glyph_origin.x), int(glyph_origin.y)) != (
                    int(legacy_origin.x),
                    int(legacy_origin.y),
                ):
                    raise RuntimeError(f"WZ glyph origin mismatch {skin_id}/{group}/{digit}")
                pixels = decode_canvas(glyph, region="GMS").convert("RGBA")
                if pixels.getbbox() is None:
                    raise RuntimeError(f"transparent WZ glyph {skin_id}/{group}/{digit}")
            for name in REQUIRED_EXTRAS.get(group, ()):
                canvas = skin.root.get(f"{group}/{name}")
                legacy = basic.root.get(f"{group}/{name}")
                if not isinstance(canvas, WzCanvasProperty) or not isinstance(legacy, WzCanvasProperty):
                    raise RuntimeError(f"required legacy damage node missing {skin_id}/{group}/{name}")
                if (int(canvas.width), int(canvas.height), int(canvas.format), int(canvas.format2)) != (
                    int(legacy.width),
                    int(legacy.height),
                    int(legacy.format),
                    int(legacy.format2),
                ):
                    raise RuntimeError(f"legacy damage node metadata mismatch {skin_id}/{group}/{name}")
                origin = canvas.child("origin")
                legacy_origin = legacy.child("origin")
                if not isinstance(origin, WzVectorProperty) or not isinstance(legacy_origin, WzVectorProperty):
                    raise RuntimeError(f"legacy damage node origin missing {skin_id}/{group}/{name}")
                if (int(origin.x), int(origin.y)) != (int(legacy_origin.x), int(legacy_origin.y)):
                    raise RuntimeError(f"legacy damage node origin mismatch {skin_id}/{group}/{name}")
                pixels = decode_canvas(canvas, region="GMS").convert("RGBA")
                if pixels.tobytes() != legacy_extra_pixels[(group, name)]:
                    raise RuntimeError(f"legacy damage node pixels mismatch {skin_id}/{group}/{name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write verified generated outputs")
    args = parser.parse_args()
    outputs, manifest = build_outputs()
    verify_outputs(outputs, manifest)
    skin_digest = hashlib.sha256()
    skin_bytes = 0
    skin_files = 0
    for path, data in outputs.items():
        if path.parent == CLIENT_SKINS:
            skin_digest.update(path.name.encode("ascii"))
            skin_digest.update(hashlib.sha256(data).digest())
            skin_bytes += len(data)
            skin_files += 1
            continue
        digest = hashlib.sha256(data).hexdigest()
        print(f"{path.relative_to(ROOT)} {len(data)} bytes sha256={digest}")
    print(
        f"{CLIENT_SKINS.relative_to(ROOT)} {skin_files} files {skin_bytes} bytes "
        f"aggregate-sha256={skin_digest.hexdigest()}"
    )
    print(f"catalog={manifest['catalogCount']} skipped={manifest['skippedCount']}")
    if args.apply:
        for path, data in outputs.items():
            atomic_write(path, data)
        print("verified damage-skin outputs written")
    else:
        print("dry-run complete; pass --apply to write outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
