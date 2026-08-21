#!/usr/bin/env python3
"""Export fixed-position Karing P2/P3 spawn cinematics as transparent MCVs."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from wzpy import WzCanvasProperty, WzImage, WzIntProperty, WzKey, WzVectorProperty  # noqa: E402

from export_soul_eclipse_mcv import (  # noqa: E402
    HEIGHT,
    WIDTH,
    encoder_command,
    read_ivf,
    write_mcv,
)


BOSS_SCRIPT = ROOT / "tool/scripts/migration/migrate_karing_p1_bosses.py"
CANVAS_ROOT = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data/Mob/_Canvas")
DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien/Data/Video"


@dataclass(frozen=True)
class PhaseScene:
    key: str
    mob_id: int
    action: str
    output_name: str
    marker_code: int
    expected_duration: int


SCENES = (
    PhaseScene("p2-regen", 8880837, "regen", "karing-p2-regen.mcv", 13, 6660),
    PhaseScene("p3-regen", 8880842, "regen", "karing-p3-regen.mcv", 14, 8100),
)


def load_boss_migration():
    spec = importlib.util.spec_from_file_location("karing_boss_migration", BOSS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def numeric_frames(node) -> list[WzCanvasProperty]:
    frames = [
        child
        for child in node.children()
        if isinstance(child, WzCanvasProperty) and child.name.isdigit()
    ]
    return sorted(frames, key=lambda frame: int(frame.name))


def frame_delay(frame: WzCanvasProperty) -> int:
    delay = frame.child("delay")
    return max(1, int(delay.value)) if isinstance(delay, WzIntProperty) else 30


def frame_origin(frame: WzCanvasProperty, fallback: WzCanvasProperty) -> tuple[int, int]:
    for candidate in (frame, fallback):
        origin = candidate.child("origin")
        if isinstance(origin, WzVectorProperty):
            return int(origin.x), int(origin.y)
    return WIDTH // 2, HEIGHT // 2


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


def load_scene(scene: PhaseScene, migration):
    proxy_path = migration.extract_source(scene.mob_id)
    proxy = migration.load_image(proxy_path, migration.BMS_KEY)
    canvas_path = CANVAS_ROOT / f"{scene.mob_id}.img"
    canvas = WzImage.from_bytes(
        canvas_path.read_bytes(), key=WzKey.for_region("BMS"), name=canvas_path.name
    )
    canvas.parse()
    if canvas.truncated or canvas.parse_warnings:
        raise RuntimeError(f"{canvas_path}: malformed {canvas.parse_warnings}")
    action = proxy.root.child(scene.action)
    if action is None:
        raise RuntimeError(f"{scene.mob_id}: missing action {scene.action}")
    frames = numeric_frames(action)
    delays = [frame_delay(frame) for frame in frames]
    if sum(delays) != scene.expected_duration:
        raise RuntimeError(
            f"{scene.key}: duration changed {sum(delays)} != {scene.expected_duration}"
        )
    return proxy_path, proxy, canvas, frames, delays


def render_frame(frame, pixel_frame, migration) -> Image.Image:
    source = migration.decode_source_canvas(pixel_frame).convert("RGBA")
    origin_x, origin_y = frame_origin(frame, pixel_frame)
    result = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    alpha_composite_clipped(
        result,
        source,
        WIDTH // 2 - origin_x,
        HEIGHT // 2 - origin_y,
    )
    source.close()
    return result


def encode_scene(scene: PhaseScene, output_directory: Path, migration) -> Path:
    proxy_path, proxy, _canvas, frames, delays = load_scene(scene, migration)
    materializer = migration.KaringCanvasMaterializer()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required")

    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"karing-{scene.key}-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(frames), color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(frames), alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg input pipes")
            for index, frame in enumerate(frames):
                pixel_frame, _, _, _ = materializer.resolve_canvas(
                    frame, proxy, proxy_path, set()
                )
                rendered = render_frame(frame, pixel_frame, migration)
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(frames):
                    print(f"encoded {scene.key}: {index + 1}/{len(frames)}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while encoding {scene.key}")
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
            raise RuntimeError(f"{scene.key}: color/alpha codec mismatch")
        output = output_directory / scene.output_name
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(
        f"wrote: {output} frames={len(delays)} "
        f"duration_ms={sum(delays)} bytes={output.stat().st_size}"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--scene", choices=("all", *(scene.key for scene in SCENES)), default="all")
    args = parser.parse_args()
    selected = SCENES if args.scene == "all" else tuple(
        scene for scene in SCENES if scene.key == args.scene
    )
    migration = load_boss_migration()
    for scene in selected:
        encode_scene(scene, args.output_directory, migration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
