#!/usr/bin/env python3
"""Export Karing boss scene screen effects as transparent MCV videos."""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
TMS_DATA = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import _encode_property_list, encode_compressed_int  # noqa: E402

from export_soul_eclipse_mcv import (  # noqa: E402
    HEIGHT,
    WIDTH,
    encoder_command,
    read_ivf,
    write_mcv,
)


DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"
CLIENT_MAP_EFFECT = ROOT / "clien" / "Data" / "Map" / "Effect.img"
FIELD_EFFECT_ROOT = "customSkill/karing"
MARKER_DURATION_MS = 500
MARKER_WIDTH = 7
MARKER_HEIGHT = 5
TMS_VIEWPORT_HEIGHT = 768
TMS_DARK_PULSE_GROUND_Y = 699


def projected_ground_offset_y() -> int:
    """Project TMS's 768px ground anchor into the 720px MCV canvas."""
    target_anchor_y = round(TMS_DARK_PULSE_GROUND_Y * HEIGHT / TMS_VIEWPORT_HEIGHT)
    return target_anchor_y - HEIGHT // 2


@dataclass(frozen=True)
class KaringSceneSpec:
    key: str
    source_path: str
    output_name: str
    marker_name: str
    marker_code: int
    anchor_offset_y: int = 0


SCENES = (
    KaringSceneSpec(
        "dark-pulse",
        "darkPulse",
        "karing-dark-pulse.mcv",
        "darkPulseVideoLayer",
        1,
        anchor_offset_y=projected_ground_offset_y(),
    ),
    KaringSceneSpec("goongi-screen", "goongiScreen", "karing-goongi-screen.mcv", "goongiScreenVideoLayer", 2),
    KaringSceneSpec(
        "perils-goongi",
        "perilsGauge/screenEff/goongi",
        "karing-perils-goongi.mcv",
        "perilsGoongiVideoLayer",
        3,
    ),
    KaringSceneSpec(
        "perils-dool",
        "perilsGauge/screenEff/dool",
        "karing-perils-dool.mcv",
        "perilsDoolVideoLayer",
        4,
    ),
    KaringSceneSpec(
        "perils-hondon",
        "perilsGauge/screenEff/hondon",
        "karing-perils-hondon.mcv",
        "perilsHondonVideoLayer",
        5,
    ),
    KaringSceneSpec("reward-screen", "rewardScreen", "karing-reward-screen.mcv", "rewardScreenVideoLayer", 6),
    KaringSceneSpec("clear-goongi", "clear/goongi", "karing-clear-goongi.mcv", "clearGoongiVideoLayer", 7),
    KaringSceneSpec("clear-goongi2", "clear/goongi2", "karing-clear-goongi2.mcv", "clearGoongi2VideoLayer", 8),
    KaringSceneSpec("clear-dool", "clear/dool", "karing-clear-dool.mcv", "clearDoolVideoLayer", 9),
    KaringSceneSpec("clear-dool2", "clear/dool2", "karing-clear-dool2.mcv", "clearDool2VideoLayer", 10),
    KaringSceneSpec("clear-hondon", "clear/hondon", "karing-clear-hondon.mcv", "clearHondonVideoLayer", 11),
    KaringSceneSpec("clear-hondon2", "clear/hondon2", "karing-clear-hondon2.mcv", "clearHondon2VideoLayer", 12),
)


def numeric_canvases(node: WzSubProperty) -> list[WzCanvasProperty]:
    frames = [
        child
        for child in node.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit()
    ]
    return sorted(frames, key=lambda frame: int(frame.name))


def frame_delay(frame: WzCanvasProperty) -> int:
    delay = frame.child("delay")
    return max(1, int(delay.value)) if isinstance(delay, WzIntProperty) else 30


def frame_origin(frame: WzCanvasProperty) -> tuple[int, int]:
    origin = frame.child("origin")
    if isinstance(origin, WzVectorProperty):
        return int(origin.x), int(origin.y)
    return WIDTH // 2, HEIGHT // 2


def load_source_images() -> tuple[WzImage, WzImage]:
    proxy_path = TMS_DATA / "Etc" / "BossKaring.img"
    canvas_path = TMS_DATA / "Etc" / "_Canvas" / "BossKaring.img"
    proxy = WzImage.from_bytes(proxy_path.read_bytes(), key=WzKey.for_region("BMS"), name=proxy_path.name)
    canvas = WzImage.from_bytes(canvas_path.read_bytes(), key=WzKey.for_region("BMS"), name=canvas_path.name)
    proxy.parse()
    canvas.parse()
    for image, path in ((proxy, proxy_path), (canvas, canvas_path)):
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"{path}: truncated={image.truncated} warnings={image.parse_warnings}")
    return proxy, canvas


def load_frames(proxy: WzImage, canvas: WzImage, spec: KaringSceneSpec) -> tuple[list[WzCanvasProperty], list[WzCanvasProperty]]:
    proxy_node = proxy.root.get(spec.source_path)
    canvas_node = canvas.root.get(spec.source_path)
    if not isinstance(proxy_node, WzSubProperty) or not isinstance(canvas_node, WzSubProperty):
        raise RuntimeError(f"missing Karing source node: {spec.source_path}")
    proxy_frames = numeric_canvases(proxy_node)
    canvas_frames = numeric_canvases(canvas_node)
    if not proxy_frames or len(proxy_frames) != len(canvas_frames):
        raise RuntimeError(
            f"Karing frame count mismatch for {spec.source_path}: "
            f"proxy={len(proxy_frames)} canvas={len(canvas_frames)}"
        )
    return proxy_frames, canvas_frames


def alpha_composite_clipped(base: Image.Image, layer: Image.Image, left: int, top: int) -> None:
    src_left = max(0, -left)
    src_top = max(0, -top)
    dst_left = max(0, left)
    dst_top = max(0, top)
    width = min(layer.width - src_left, base.width - dst_left)
    height = min(layer.height - src_top, base.height - dst_top)
    if width <= 0 or height <= 0:
        return
    cropped = layer.crop((src_left, src_top, src_left + width, src_top + height))
    base.alpha_composite(cropped, (dst_left, dst_top))
    cropped.close()


def render_frame(
    proxy_frame: WzCanvasProperty,
    canvas_frame: WzCanvasProperty,
    anchor_offset_y: int = 0,
) -> Image.Image:
    source = decode_canvas(canvas_frame, region="BMS").convert("RGBA")
    origin_x, origin_y = frame_origin(proxy_frame)
    left = WIDTH // 2 - origin_x
    top = HEIGHT // 2 + anchor_offset_y - origin_y
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    alpha_composite_clipped(result, source, left, top)
    source.close()
    return result


def encode_scene(proxy: WzImage, canvas: WzImage, spec: KaringSceneSpec, output_directory: Path) -> Path:
    proxy_frames, canvas_frames = load_frames(proxy, canvas, spec)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export Karing MCV files")
    delays = [frame_delay(frame) for frame in proxy_frames]
    with tempfile.TemporaryDirectory(prefix=f"karing-{spec.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(proxy_frames), color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(proxy_frames), alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg input pipes")
            for index, (proxy_frame, canvas_frame) in enumerate(zip(proxy_frames, canvas_frames)):
                rendered = render_frame(
                    proxy_frame, canvas_frame, spec.anchor_offset_y
                )
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(proxy_frames):
                    print(f"encoded {spec.key}: {index + 1}/{len(proxy_frames)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while encoding {spec.key}")
        except BaseException:
            for process in (color, alpha):
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            raise

        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError(f"color and alpha codecs do not match for {spec.key}")
        output = output_directory / spec.output_name
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} bytes={output.stat().st_size}")
    return output


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    node = root
    for name in path.split("/"):
        child = node.child(name)
        if not isinstance(child, WzSubProperty):
            child = WzSubProperty(name, node)
            node.add(child)
        node = child
    return node


def replace_child(parent: WzSubProperty, child: WzSubProperty) -> None:
    parent._children.pop(child.name, None)
    parent.add(child)


def marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    if marker_code < 1 or marker_code > 255:
        raise RuntimeError(f"invalid Karing marker code: {marker_code}")
    return [
        (34, 17, 68, 255),
        (68, 85, 119, 255),
        (153, 170, 187, 255),
        (204, 221, 221, 255),
        (marker_code * 17, 85, 187, 255),
    ] + [(0, 0, 0, 0)] * (MARKER_WIDTH * MARKER_HEIGHT - 5)


def decoded_marker_pixels(marker_code: int) -> list[tuple[int, int, int, int]]:
    return [
        (34, 17, 68, 255),
        (68, 85, 119, 255),
        (153, 170, 187, 255),
        (204, 221, 221, 255),
        (marker_code * 17, 85, 187, 255),
    ] + [(0, 0, 0, 0)] * (MARKER_WIDTH * MARKER_HEIGHT - 5)


def build_marker(parent: WzSubProperty, spec: KaringSceneSpec, key: WzKey) -> WzSubProperty:
    effect = WzSubProperty(spec.marker_name, parent)
    image = Image.new("RGBA", (MARKER_WIDTH, MARKER_HEIGHT), (0, 0, 0, 0))
    image.putdata(marker_pixels(spec.marker_code))
    frame = WzCanvasProperty("0", effect)
    frame.width = MARKER_WIDTH
    frame.height = MARKER_HEIGHT
    frame.format = 1
    frame.format2 = 0
    frame._png_data = encode_canvas_payload(
        image,
        1,
        MARKER_WIDTH,
        MARKER_HEIGHT,
        key=key,
        listwz=False,
        zlib_level=9,
    )
    frame._png_length = len(frame._png_data)
    frame._png_offset = 0
    frame.add(WzVectorProperty("origin", MARKER_WIDTH // 2, MARKER_HEIGHT // 2, frame))
    frame.add(WzIntProperty("delay", MARKER_DURATION_MS, frame))
    frame.add(WzIntProperty("z", 0, frame))
    effect.add(frame)
    image.close()
    return effect


def locate_nested_property_records(
    image: WzImage,
    data: bytes,
    parent_path: tuple[str, ...],
) -> tuple[tuple[int, ...], int, int, tuple[str, ...], tuple[tuple[int, int], ...], int]:
    reader = image.wz_file.reader
    reader.seek(0)
    if reader.read_byte() != 0x73 or reader.read_string() != "Property":
        raise RuntimeError(f"unsupported standalone IMG header: {image.name}")
    reader.skip(2)

    def descend(segments: tuple[str, ...], block_end: int, size_offsets: tuple[int, ...]):
        count = reader.read_compressed_int()
        for _ in range(count):
            name = reader.read_string_block(0)
            tag = reader.read_byte()
            if tag != 9:
                raise RuntimeError(
                    f"unexpected property tag in {'/'.join(parent_path)}: {name}/{tag}"
                )
            size_offset = reader.position
            block_size = reader.read_u32()
            child_start = reader.position
            child_end = child_start + block_size
            if name != segments[0]:
                reader.seek(child_end)
                continue
            reader.seek(child_start)
            if reader.read_string_block(0) != "Property":
                raise RuntimeError(f"property is not a container: {name}")
            reader.skip(2)
            next_offsets = (*size_offsets, size_offset)
            if len(segments) > 1:
                return descend(segments[1:], child_end, next_offsets)

            child_count_offset = reader.position
            child_count = reader.read_compressed_int()
            child_count_end = reader.position
            names = []
            spans = []
            for _ in range(child_count):
                record_start = reader.position
                child_name = reader.read_string_block(0)
                child_tag = reader.read_byte()
                if child_tag != 9:
                    raise RuntimeError(
                        f"unexpected child tag in {'/'.join(parent_path)}: "
                        f"{child_name}/{child_tag}"
                    )
                child_size = reader.read_u32()
                reader.seek(reader.position + child_size)
                names.append(child_name)
                spans.append((record_start, reader.position))
            if reader.position != child_end:
                raise RuntimeError(
                    f"property records do not fill {'/'.join(parent_path)}"
                )
            return (
                next_offsets,
                child_count_offset,
                child_count_end,
                tuple(names),
                tuple(spans),
                child_end,
            )
        reader.seek(block_end)
        raise RuntimeError(f"missing property path: {'/'.join(parent_path)}")

    return descend(parent_path, len(data), ())


def encode_property_record(node: WzSubProperty, image: WzImage) -> bytes:
    encoded = _encode_property_list((node,), image.wz_file.reader)
    prefix = encode_compressed_int(1)
    if not encoded.startswith(prefix):
        raise RuntimeError("unexpected Karing property record prefix")
    return encoded[len(prefix):]


def patch_karing_record(image: WzImage, original: bytes, parent: WzSubProperty) -> bytes:
    replacement = encode_property_record(parent, image)
    (size_offsets, count_offset, count_end,
     names, spans, records_end) = locate_nested_property_records(
        image, original, ("customSkill",)
    )
    original_records = {
        name: original[start:end]
        for name, (start, end) in zip(names, spans)
    }
    if "karing" in original_records:
        index = names.index("karing")
        record_start, record_end = spans[index]
        updated = bytearray(
            original[:record_start] + replacement + original[record_end:]
        )
        count_delta = 0
    else:
        updated = bytearray(
            original[:records_end] + replacement + original[records_end:]
        )
        count_delta = 1

    size_delta = len(updated) - len(original)
    if count_delta:
        new_count = encode_compressed_int(len(names) + count_delta)
        if len(new_count) != count_end - count_offset:
            raise RuntimeError("customSkill child-count encoding size changed")
        updated[count_offset:count_end] = new_count
    for size_offset in size_offsets:
        old_size = struct.unpack_from("<I", original, size_offset)[0]
        struct.pack_into("<I", updated, size_offset, old_size + size_delta)

    verified = WzImage.from_bytes(
        bytes(updated), key=WzKey.for_region("GMS"), name=CLIENT_MAP_EFFECT.name
    )
    verified.parse()
    if verified.truncated or verified.parse_warnings:
        raise RuntimeError(
            f"incremental Effect.img patch is malformed: {verified.parse_warnings}"
        )
    (_, _, _, verified_names,
     verified_spans, _) = locate_nested_property_records(
        verified, bytes(updated), ("customSkill",)
    )
    verified_records = {
        name: bytes(updated)[start:end]
        for name, (start, end) in zip(verified_names, verified_spans)
    }
    for name, record in original_records.items():
        if name != "karing" and verified_records.get(name) != record:
            raise RuntimeError(f"unchanged customSkill record changed: {name}")
    return bytes(updated)


def install_markers(selected: tuple[KaringSceneSpec, ...], dry_run: bool) -> None:
    original = CLIENT_MAP_EFFECT.read_bytes()
    image = WzImage.from_bytes(
        original,
        key=WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    )
    root = image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{CLIENT_MAP_EFFECT}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    parent = ensure_path(root, FIELD_EFFECT_ROOT)
    key = image.wz_file.reader.key
    for spec in selected:
        replace_child(parent, build_marker(parent, spec, key))
        print(f"field effect marker: {FIELD_EFFECT_ROOT}/{spec.marker_name}")
    updated = patch_karing_record(image, original, parent)
    if dry_run:
        return
    temporary = CLIENT_MAP_EFFECT.with_name(f".{CLIENT_MAP_EFFECT.name}.karing.tmp")
    temporary.write_bytes(updated)
    temporary.replace(CLIENT_MAP_EFFECT)


def verify_markers(selected: tuple[KaringSceneSpec, ...]) -> None:
    image = WzImage.from_bytes(
        CLIENT_MAP_EFFECT.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=CLIENT_MAP_EFFECT.name,
    )
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"{CLIENT_MAP_EFFECT}: truncated={image.truncated} warnings={image.parse_warnings}"
        )
    for spec in selected:
        frame = image.root.get(f"{FIELD_EFFECT_ROOT}/{spec.marker_name}/0")
        if not isinstance(frame, WzCanvasProperty):
            raise RuntimeError(f"missing Karing marker: {spec.marker_name}")
        if int(frame.width) != MARKER_WIDTH or int(frame.height) != MARKER_HEIGHT:
            raise RuntimeError(f"invalid Karing marker size: {spec.marker_name}")
        z = frame.child("z")
        if not isinstance(z, WzIntProperty) or int(z.value) != 0:
            raise RuntimeError(f"invalid Karing marker z-order: {spec.marker_name}")
        delay = frame.child("delay")
        if not isinstance(delay, WzIntProperty) or int(delay.value) != MARKER_DURATION_MS:
            raise RuntimeError(f"invalid Karing marker duration: {spec.marker_name}")
        decoded = decode_canvas(frame, region="GMS").convert("RGBA")
        if list(decoded.getdata())[:5] != decoded_marker_pixels(spec.marker_code)[:5]:
            raise RuntimeError(f"Karing marker signature mismatch: {spec.marker_name}")
        decoded.close()


def selected_scenes(effect: str) -> tuple[KaringSceneSpec, ...]:
    if effect == "all":
        return SCENES
    return tuple(spec for spec in SCENES if spec.key == effect)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--effect", choices=("all", *(spec.key for spec in SCENES)), default="all")
    parser.add_argument("--markers-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    selected = selected_scenes(args.effect)
    if not args.markers_only:
        proxy, canvas = load_source_images()
        args.output_directory.mkdir(parents=True, exist_ok=True)
        for spec in selected:
            encode_scene(proxy, canvas, spec, args.output_directory)
    if not args.videos_only:
        install_markers(selected, args.dry_run)
        if not args.dry_run:
            verify_markers(selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
