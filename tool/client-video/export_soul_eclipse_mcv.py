#!/usr/bin/env python3
"""Export the existing formal Soul Eclipse Canvas effect as an MCV video."""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(WZPY))

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import (  # noqa: E402
    WzCanvasProperty,
    WzIntProperty,
    WzSubProperty,
    WzVectorProperty,
)


WIDTH = 1280
HEIGHT = 720
FRAME_RATE = 30
MCV_HEADER_SIZE = 36
FOURCC_XOR = 0xA5A5A5A5
SOURCE_NODE = "customSkill/dawnWarrior/soulEclipse"
DEFAULT_SOURCE = ROOT / "clien" / "Data" / "Map" / "Effect.img"
DEFAULT_OUTPUT = ROOT / "clien" / "Data" / "Video" / "soul-eclipse.mcv"


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
    return int(frame.width) // 2, int(frame.height) // 2


def load_frames(path: Path, source_node: str = SOURCE_NODE) -> tuple[WzImage, list[WzCanvasProperty]]:
    image = WzImage.from_bytes(
        path.read_bytes(),
        key=WzKey.for_region("GMS"),
        name=path.name,
    )
    node = image.parse().get(source_node)
    if not isinstance(node, WzSubProperty):
        raise RuntimeError(f"missing source effect: {source_node}")
    frames = numeric_canvases(node)
    if not frames:
        raise RuntimeError(f"source effect has no numeric Canvas frames: {source_node}")
    return image, frames


def render_frame(
    frame: WzCanvasProperty,
    background: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    source = decode_canvas(frame, region="GMS").convert("RGBA")
    origin_x, origin_y = frame_origin(frame)
    left = WIDTH // 2 - origin_x
    top = HEIGHT // 2 - origin_y
    result = Image.new("RGBA", (WIDTH, HEIGHT), background or (0, 0, 0, 0))
    result.alpha_composite(source, (left, top))
    source.close()
    return result


def encoder_command(
    ffmpeg: str,
    pixel_format: str,
    crf: int,
    frame_count: int,
    output: Path,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        pixel_format,
        "-video_size",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        str(FRAME_RATE),
        "-i",
        "pipe:0",
        "-frames:v",
        str(frame_count),
        "-an",
        "-c:v",
        "libvpx-vp9",
        "-deadline",
        "good",
        "-cpu-used",
        "4",
        "-row-mt",
        "1",
        "-tile-columns",
        "2",
        "-threads",
        "8",
        "-lag-in-frames",
        "0",
        "-auto-alt-ref",
        "0",
        "-g",
        str(frame_count),
        "-crf",
        str(crf),
        "-b:v",
        "0",
        "-pix_fmt",
        "yuv420p",
        "-f",
        "ivf",
        str(output),
    ]


def encode_streams(
    frames: list[WzCanvasProperty],
    color_path: Path,
    alpha_path: Path,
    background: tuple[int, int, int, int] | None = None,
) -> list[int]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export the MCV resource")
    color = subprocess.Popen(
        encoder_command(ffmpeg, "rgb24", 24, len(frames), color_path),
        stdin=subprocess.PIPE,
    )
    alpha = subprocess.Popen(
        encoder_command(ffmpeg, "gray", 16, len(frames), alpha_path),
        stdin=subprocess.PIPE,
    )
    delays: list[int] = []
    try:
        if color.stdin is None or alpha.stdin is None:
            raise RuntimeError("failed to open FFmpeg input pipes")
        for index, frame in enumerate(frames):
            rendered = render_frame(frame, background)
            color.stdin.write(rendered.convert("RGB").tobytes())
            alpha.stdin.write(rendered.getchannel("A").tobytes())
            rendered.close()
            delays.append(frame_delay(frame))
            if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(frames):
                print(f"encoded source frames: {index + 1}/{len(frames)}", flush=True)
        color.stdin.close()
        alpha.stdin.close()
        if color.wait() != 0 or alpha.wait() != 0:
            raise RuntimeError("FFmpeg failed while encoding Soul Eclipse streams")
    except BaseException:
        for process in (color, alpha):
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                process.wait()
        raise
    return delays


def read_ivf(path: Path) -> tuple[bytes, list[bytes]]:
    data = path.read_bytes()
    if len(data) < 32 or data[:4] != b"DKIF":
        raise RuntimeError(f"invalid IVF output: {path}")
    header_size = struct.unpack_from("<H", data, 6)[0]
    fourcc = data[8:12]
    if header_size < 32 or fourcc != b"VP90":
        raise RuntimeError(f"unexpected IVF format: header={header_size}, codec={fourcc!r}")
    packets: list[bytes] = []
    position = header_size
    while position < len(data):
        if len(data) - position < 12:
            raise RuntimeError(f"truncated IVF packet header: {path}")
        packet_size = struct.unpack_from("<I", data, position)[0]
        position += 12
        if packet_size == 0 or packet_size > len(data) - position:
            raise RuntimeError(f"invalid IVF packet size: {packet_size}")
        packets.append(data[position : position + packet_size])
        position += packet_size
    return fourcc, packets


def write_mcv(
    path: Path,
    fourcc: bytes,
    color_packets: list[bytes],
    alpha_packets: list[bytes],
    delays: list[int],
) -> None:
    frame_count = len(delays)
    if len(color_packets) != frame_count or len(alpha_packets) != frame_count:
        raise RuntimeError(
            "encoded packet count mismatch: "
            f"frames={frame_count}, color={len(color_packets)}, alpha={len(alpha_packets)}"
        )
    encoded_fourcc = struct.unpack("<I", fourcc)[0] ^ FOURCC_XOR
    header = struct.pack(
        "<4sHHIHHIB3xQI",
        b"MCV0",
        0,
        MCV_HEADER_SIZE,
        encoded_fourcc,
        WIDTH,
        HEIGHT,
        frame_count,
        3,
        1_000_000,
        0,
    )
    color_offsets: list[int] = []
    alpha_offsets: list[int] = []
    offset = 0
    for packet in color_packets:
        color_offsets.append(offset)
        offset += len(packet)
    for packet in alpha_packets:
        alpha_offsets.append(offset)
        offset += len(packet)
    if offset > 0xFFFFFFFF:
        raise RuntimeError("MCV payload exceeds the 32-bit format limit")

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as output:
        temporary = Path(output.name)
        output.write(header)
        for offset, packet in zip(color_offsets, color_packets):
            output.write(struct.pack("<II", offset, len(packet)))
        for offset, packet in zip(alpha_offsets, alpha_packets):
            output.write(struct.pack("<II", offset, len(packet)))
        for delay in delays:
            output.write(struct.pack("<I", delay))
        for packet in color_packets:
            output.write(packet)
        for packet in alpha_packets:
            output.write(packet)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    image, frames = load_frames(args.source)
    print(f"source effect: frames={len(frames)}, duration_ms={sum(map(frame_delay, frames))}")
    with tempfile.TemporaryDirectory(prefix="soul-eclipse-mcv-") as directory:
        temporary = Path(directory)
        color_path = temporary / "color.ivf"
        alpha_path = temporary / "alpha.ivf"
        delays = encode_streams(frames, color_path, alpha_path)
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError("color and alpha codecs do not match")
        write_mcv(args.output, color_fourcc, color_packets, alpha_packets, delays)
    del image
    print(f"wrote: {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
