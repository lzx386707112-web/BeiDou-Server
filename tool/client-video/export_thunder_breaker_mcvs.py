#!/usr/bin/env python3
"""Encode Thunder Breaker VI full-screen effects as transparent MCV videos."""

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
PATCH_SKILL = ROOT / "tool" / "scripts" / "patch-skill"
WZPY = ROOT / "tool" / "wz-python"
sys.path.insert(0, str(PATCH_SKILL))
sys.path.insert(0, str(WZPY))

from export_soul_eclipse_mcv import (  # noqa: E402
    HEIGHT,
    WIDTH,
    encoder_command,
    read_ivf,
    write_mcv,
)
from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.properties import WzSubProperty, WzVideoProperty  # noqa: E402

import export_thunder_breaker_ms as ms_export  # noqa: E402
import patch_thunder_breaker_v_vi as thunder_breaker  # noqa: E402


DEFAULT_OUTPUT_DIRECTORY = ROOT / "clien" / "Data" / "Video"


@dataclass(frozen=True)
class McvTrack:
    fourcc: bytes
    width: int
    height: int
    color_packets: tuple[bytes, ...]
    alpha_packets: tuple[bytes, ...]
    delays: tuple[int, ...]


@dataclass
class RawDecoder:
    process: subprocess.Popen
    frame_count: int
    width: int
    height: int

    def read_frame(self, index: int) -> Image.Image | None:
        if index >= self.frame_count:
            return None
        if self.process.stdout is None:
            raise RuntimeError("FFmpeg decoder stdout is unavailable")
        frame_bytes = self.width * self.height * 4
        data = self.process.stdout.read(frame_bytes)
        if len(data) != frame_bytes:
            raise RuntimeError(f"FFmpeg returned a truncated RGBA frame: {len(data)} bytes")
        return Image.frombytes("RGBA", (self.width, self.height), data)

    def close(self) -> None:
        if self.process.stdout is not None:
            self.process.stdout.close()
        if self.process.wait() != 0:
            raise RuntimeError("FFmpeg failed while decoding a source MCV")


def parse_mcv(data: bytes) -> McvTrack:
    if len(data) < 36 or data[:4] != b"MCV0":
        raise RuntimeError("invalid source MCV header")
    header_length = struct.unpack_from("<H", data, 6)[0]
    encoded_fourcc = struct.unpack_from("<I", data, 8)[0]
    fourcc = struct.pack("<I", encoded_fourcc ^ 0xA5A5A5A5)
    width, height = struct.unpack_from("<HH", data, 12)
    frame_count = struct.unpack_from("<I", data, 16)[0]
    flags = data[20]
    delay_unit = struct.unpack_from("<Q", data, 24)[0]
    default_delay = struct.unpack_from("<I", data, 32)[0]
    if flags & ~0x07 or not frame_count:
        raise RuntimeError(f"unsupported source MCV flags/count: {flags:#x}/{frame_count}")
    position = header_length

    def read_table() -> list[tuple[int, int]]:
        nonlocal position
        table = []
        for _ in range(frame_count):
            table.append(struct.unpack_from("<II", data, position))
            position += 8
        return table

    color_table = read_table()
    alpha_table = read_table() if flags & 0x01 else [(0, 0)] * frame_count
    if flags & 0x02:
        delay_values = struct.unpack_from(f"<{frame_count}I", data, position)
        position += frame_count * 4
    else:
        delay_values = (default_delay,) * frame_count
    if flags & 0x04:
        position += frame_count * 8
    data_start = position

    def packets(table: list[tuple[int, int]]) -> tuple[bytes, ...]:
        result = []
        for offset, size in table:
            start = data_start + offset
            end = start + size
            if size <= 0 or start < data_start or end > len(data):
                raise RuntimeError("source MCV frame payload is out of bounds")
            result.append(data[start:end])
        return tuple(result)

    delays = tuple(max(1, round(value * delay_unit / 1_000_000)) for value in delay_values)
    return McvTrack(
        fourcc, width, height, packets(color_table), packets(alpha_table), delays
    )


def write_ivf(path: Path, track: McvTrack, packets: tuple[bytes, ...]) -> None:
    with path.open("wb") as output:
        output.write(struct.pack(
            "<4sHH4sHHIIII", b"DKIF", 0, 32, track.fourcc,
            track.width, track.height, 1000, 1, len(packets), 0,
        ))
        for index, packet in enumerate(packets):
            output.write(struct.pack("<IQ", len(packet), index))
            output.write(packet)


def start_decoder(
        ffmpeg: str,
        track: McvTrack,
        directory: Path,
        index: int,
        cover_bounds: tuple[int, int, int, int] | None = None,
) -> RawDecoder:
    color = directory / f"track-{index}-color.ivf"
    alpha = directory / f"track-{index}-alpha.ivf"
    write_ivf(color, track, track.color_packets)
    write_ivf(alpha, track, track.alpha_packets)
    if cover_bounds is None:
        color_filter = "format=rgba"
        alpha_filter = "format=gray"
        output_width = track.width
        output_height = track.height
    else:
        left, top, right, bottom = cover_bounds
        crop_width = right - left
        crop_height = bottom - top
        if (crop_width <= 0 or crop_height <= 0
                or left < 0 or top < 0
                or right > track.width or bottom > track.height):
            raise RuntimeError(f"invalid source Alpha bounds: {cover_bounds}")
        cover = (
            f"crop={crop_width}:{crop_height}:{left}:{top},"
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}:(iw-ow)/2:(ih-oh)/2"
        )
        color_filter = f"{cover},format=rgba"
        alpha_filter = f"{cover},format=gray"
        output_width = WIDTH
        output_height = HEIGHT
    command = [
        ffmpeg, "-v", "error", "-i", str(color), "-i", str(alpha),
        "-filter_complex",
        f"[0:v]{color_filter}[c];[1:v]{alpha_filter}[a];"
        "[c][a]alphamerge,format=rgba[out]",
        "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "rgba", "-",
    ]
    return RawDecoder(
        subprocess.Popen(command, stdout=subprocess.PIPE),
        len(track.delays),
        output_width,
        output_height,
    )


def union_alpha_bounds(
        current: tuple[int, int, int, int] | None,
        frame: Image.Image,
) -> tuple[int, int, int, int] | None:
    bounds = frame.getchannel("A").getbbox()
    if bounds is None:
        return current
    if current is None:
        return bounds
    return (
        min(current[0], bounds[0]),
        min(current[1], bounds[1]),
        max(current[2], bounds[2]),
        max(current[3], bounds[3]),
    )


def decoded_alpha_union_bounds(
        tracks: tuple[McvTrack, ...],
        ffmpeg: str,
        directory: Path,
) -> tuple[int, int, int, int]:
    dimensions = {(track.width, track.height) for track in tracks}
    if len(dimensions) != 1:
        raise RuntimeError(f"source video dimensions do not match: {sorted(dimensions)}")
    decoders = [
        start_decoder(ffmpeg, track, directory, index)
        for index, track in enumerate(tracks)
    ]
    bounds = None
    try:
        for decoder in decoders:
            for frame_index in range(decoder.frame_count):
                frame = decoder.read_frame(frame_index)
                if frame is not None:
                    bounds = union_alpha_bounds(bounds, frame)
                    frame.close()
        for decoder in decoders:
            decoder.close()
    except BaseException:
        for decoder in decoders:
            if decoder.process.poll() is None:
                decoder.process.terminate()
                decoder.process.wait()
        raise
    if bounds is None:
        raise RuntimeError("source full-screen video has no visible Alpha pixels")
    return bounds


def output_alpha_union_bounds(path: Path, ffmpeg: str) -> tuple[int, int, int, int]:
    track = parse_mcv(path.read_bytes())
    if (track.width, track.height) != (WIDTH, HEIGHT):
        raise RuntimeError(
            f"unexpected output dimensions for {path}: {track.width}x{track.height}"
        )
    with tempfile.TemporaryDirectory(prefix="thunder-breaker-alpha-check-") as name:
        return decoded_alpha_union_bounds((track,), ffmpeg, Path(name))


def encode_tracks(
        key: str,
        tracks: tuple[McvTrack, ...],
        output: Path,
        ffmpeg: str,
) -> Path:
    frame_count = max(len(track.delays) for track in tracks)
    delays = list(tracks[0].delays)
    if len(delays) < frame_count:
        delays.extend([delays[-1]] * (frame_count - len(delays)))
    with tempfile.TemporaryDirectory(prefix=f"{key}-mcv-") as directory_name:
        directory = Path(directory_name)
        dimensions = {(track.width, track.height) for track in tracks}
        if len(dimensions) == 1:
            cover_bounds = decoded_alpha_union_bounds(tracks, ffmpeg, directory)
            cover_bounds_by_track = [cover_bounds] * len(tracks)
        else:
            cover_bounds_by_track = [
                decoded_alpha_union_bounds((track,), ffmpeg, directory)
                for track in tracks
            ]
        decoders = [
            start_decoder(ffmpeg, track, directory, index, cover_bounds)
            for index, (track, cover_bounds) in enumerate(zip(tracks, cover_bounds_by_track))
        ]
        color_path = directory / "color.ivf"
        alpha_path = directory / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, frame_count, color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, frame_count, alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open FFmpeg encoder pipes")
            for frame_index in range(frame_count):
                rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                for decoder in decoders:
                    layer = decoder.read_frame(frame_index)
                    if layer is not None:
                        rendered.alpha_composite(layer)
                        layer.close()
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if frame_index == 0 or (frame_index + 1) % 20 == 0 or frame_index + 1 == frame_count:
                    print(f"encoded {key}: {frame_index + 1}/{frame_count}", flush=True)
            color.stdin.close()
            alpha.stdin.close()
            for decoder in decoders:
                decoder.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError(f"FFmpeg failed while encoding {key}")
        except BaseException:
            for process in [*(decoder.process for decoder in decoders), color, alpha]:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            raise
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        if color_fourcc != alpha_fourcc:
            raise RuntimeError("color and alpha codecs do not match")
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    output_bounds = output_alpha_union_bounds(output, ffmpeg)
    if output_bounds != (0, 0, WIDTH, HEIGHT):
        raise RuntimeError(
            f"output video does not cover the full canvas: {key} {output_bounds}"
        )
    print(f"wrote: {output} frames={frame_count} duration_ms={sum(delays)} bytes={output.stat().st_size}")
    return output


def source_video(image: WzImage, root: WzSubProperty, skill_id: int, path: str) -> McvTrack:
    node = root.get(f"skill/{skill_id}/{path}")
    if not isinstance(node, WzVideoProperty):
        raise RuntimeError(f"missing source video: {skill_id}/{path}")
    reader = image.wz_file.reader
    saved = reader.position
    try:
        reader.seek(node._data_offset)
        data = reader.read(node._data_length)
    finally:
        reader.seek(saved)
    return parse_mcv(data)


def encode_source_videos(output_directory: Path, ffmpeg: str) -> None:
    with tempfile.TemporaryDirectory(prefix="thunder-breaker-source-") as directory_name:
        directory = Path(directory_name)
        pack, prefix = ms_export.GROUPS["1514"]
        subprocess.run(
            ["/opt/homebrew/bin/dotnet", str(ms_export.MS_PROBE), str(pack), str(directory), prefix],
            check=True,
        )
        extracted = directory / "Skill_1514.img"
        image = WzImage.from_bytes(
            extracted.read_bytes(), key=WzKey.for_region("BMS"), name=extracted.name
        )
        root = image.parse()
        encode_tracks(
            "wave-riding-thunder",
            (source_video(image, root, 15141500, "screen/video"),),
            output_directory / "wave-riding-thunder.mcv",
            ffmpeg,
        )
        encode_tracks(
            "swift-annihilation",
            (
                source_video(image, root, 15141502, "screen/video"),
                source_video(image, root, 15141502, "screen2/video"),
                source_video(image, root, 15141502, "screen3/video"),
            ),
            output_directory / "swift-annihilation.mcv",
            ffmpeg,
        )


def encode_god_of_sea(output_directory: Path, ffmpeg: str) -> Path:
    thunder_breaker.configure_engine()
    groups, _, metadata = thunder_breaker.engine.load_sources()
    screen_meta = thunder_breaker.source_metadata_node(
        metadata, 15141007, "screen"
    )
    frame_metadata = thunder_breaker.engine.base.ms_numeric_frames(
        screen_meta, metadata
    )
    if not frame_metadata:
        raise RuntimeError("unexpected God of the Sea VI screen track")
    screen_timeline = []
    elapsed = 0
    for meta in frame_metadata:
        delay = thunder_breaker.engine.base.ms_int(meta, "delay", 60) or 60
        screen_timeline.append((elapsed, elapsed + delay, meta))
        elapsed += delay

    flash_meta = thunder_breaker.source_metadata_node(
        metadata, 15141007, "effectFlash"
    )
    flash_timeline = []
    elapsed = 0
    flash_entries = sorted(
        (child for child in flash_meta
         if child.tag == "imgdir" and child.attrib.get("name", "").isdigit()),
        key=lambda child: int(child.attrib["name"]),
    )
    for entry in flash_entries:
        delay = thunder_breaker.engine.base.ms_int(entry, "delay", 0) or 0
        alpha = thunder_breaker.engine.base.ms_int(entry, "alpha", 0) or 0
        color_node = next(
            (child for child in entry
             if child.tag == "string" and child.attrib.get("name") == "color"),
            None,
        )
        color_text = "0" if color_node is None else color_node.attrib["value"]
        color_value = int(color_text, 16)
        color = (
            (color_value >> 16) & 0xFF,
            (color_value >> 8) & 0xFF,
            color_value & 0xFF,
        )
        flash_timeline.append((elapsed, elapsed + delay, color, alpha))
        elapsed += delay

    boundaries = sorted({
        time
        for timeline in (screen_timeline, flash_timeline)
        for entry in timeline
        for time in entry[:2]
    })
    screen_end = screen_timeline[-1][1]
    boundaries = [time for time in boundaries if time <= screen_end]
    delays = [end - begin for begin, end in zip(boundaries, boundaries[1:])]
    segments = list(zip(boundaries, boundaries[1:]))
    with tempfile.TemporaryDirectory(prefix="god-of-sea-vi-mcv-") as directory_name:
        directory = Path(directory_name)
        color_path = directory / "color.ivf"
        alpha_path = directory / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(segments), color_path),
            stdin=subprocess.PIPE,
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(segments), alpha_path),
            stdin=subprocess.PIPE,
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open God of the Sea VI encoder pipes")
            for index, (begin, _end) in enumerate(segments):
                rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                meta = next(
                    entry[2] for entry in screen_timeline
                    if entry[0] <= begin < entry[1]
                )
                canvas = thunder_breaker.engine.base.resolve_ms_canvas(
                    meta, groups, metadata
                )
                if canvas is not None:
                    layer = thunder_breaker.engine.base.clean_rgba(
                        thunder_breaker.engine.base.decode_source_canvas(canvas)
                    )
                    origin_x, origin_y = thunder_breaker.engine.base.canvas_origin(
                        canvas, meta
                    )
                    rendered.alpha_composite(
                        layer, (WIDTH // 2 - origin_x, HEIGHT // 2 - origin_y)
                    )
                    layer.close()
                flash = next(
                    (entry for entry in flash_timeline
                     if entry[0] <= begin < entry[1]),
                    None,
                )
                if flash is not None and flash[3] > 0:
                    # TMS effectFlash alpha is expressed as a percentage.
                    overlay_alpha = max(0, min(255, round(flash[3] * 255 / 100)))
                    overlay = Image.new(
                        "RGBA", (WIDTH, HEIGHT), (*flash[2], overlay_alpha)
                    )
                    rendered.alpha_composite(overlay)
                    overlay.close()
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if (index == 0 or (index + 1) % 20 == 0
                        or index + 1 == len(segments)):
                    print(
                        f"encoded god-of-sea-vi: {index + 1}/{len(segments)}",
                        flush=True,
                    )
            color.stdin.close()
            alpha.stdin.close()
            if color.wait() != 0 or alpha.wait() != 0:
                raise RuntimeError("FFmpeg failed while encoding God of the Sea VI")
        except BaseException:
            for process in (color, alpha):
                if process.poll() is None:
                    process.terminate()
                    process.wait()
            raise
        color_fourcc, color_packets = read_ivf(color_path)
        alpha_fourcc, alpha_packets = read_ivf(alpha_path)
        output = output_directory / "god-of-sea-vi.mcv"
        write_mcv(output, color_fourcc, color_packets, alpha_packets, delays)
    print(
        f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} "
        f"effect_flash_frames={len(flash_entries)} bytes={output.stat().st_size}"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument(
        "--effect",
        choices=("all", "god-of-sea-vi", "wave-riding-thunder", "swift-annihilation"),
        default="all",
    )
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to export MCV files")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    if args.effect in {"all", "god-of-sea-vi"}:
        encode_god_of_sea(args.output_directory, ffmpeg)
    if args.effect in {"all", "wave-riding-thunder", "swift-annihilation"}:
        encode_source_videos(args.output_directory, ffmpeg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
