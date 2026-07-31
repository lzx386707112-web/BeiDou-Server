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
FRAME_BYTES = WIDTH * HEIGHT * 4


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

    def read_frame(self, index: int) -> Image.Image | None:
        if index >= self.frame_count:
            return None
        if self.process.stdout is None:
            raise RuntimeError("FFmpeg decoder stdout is unavailable")
        data = self.process.stdout.read(FRAME_BYTES)
        if len(data) != FRAME_BYTES:
            raise RuntimeError(f"FFmpeg returned a truncated RGBA frame: {len(data)} bytes")
        return Image.frombytes("RGBA", (WIDTH, HEIGHT), data)

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


def start_decoder(ffmpeg: str, track: McvTrack, directory: Path, index: int) -> RawDecoder:
    color = directory / f"track-{index}-color.ivf"
    alpha = directory / f"track-{index}-alpha.ivf"
    write_ivf(color, track, track.color_packets)
    write_ivf(alpha, track, track.alpha_packets)
    contain = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2"
    )
    command = [
        ffmpeg, "-v", "error", "-i", str(color), "-i", str(alpha),
        "-filter_complex",
        f"[0:v]{contain},format=rgba[c];[1:v]{contain},format=gray[a];"
        "[c][a]alphamerge,format=rgba[out]",
        "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "rgba", "-",
    ]
    return RawDecoder(subprocess.Popen(command, stdout=subprocess.PIPE), len(track.delays))


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
        decoders = [start_decoder(ffmpeg, track, directory, index) for index, track in enumerate(tracks)]
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
    variants = thunder_breaker.engine.tracks(groups, metadata, 15141007, "screen")
    if len(variants) != 1 or not variants[0]:
        raise RuntimeError("unexpected God of the Sea VI screen track")
    track = variants[0]
    delays = [thunder_breaker.engine.base.frame_delay(canvas, meta) for canvas, meta in track]
    with tempfile.TemporaryDirectory(prefix="god-of-sea-vi-mcv-") as directory_name:
        directory = Path(directory_name)
        color_path = directory / "color.ivf"
        alpha_path = directory / "alpha.ivf"
        color = subprocess.Popen(
            encoder_command(ffmpeg, "rgb24", 24, len(track), color_path), stdin=subprocess.PIPE
        )
        alpha = subprocess.Popen(
            encoder_command(ffmpeg, "gray", 16, len(track), alpha_path), stdin=subprocess.PIPE
        )
        try:
            if color.stdin is None or alpha.stdin is None:
                raise RuntimeError("failed to open God of the Sea VI encoder pipes")
            for index, (canvas, meta) in enumerate(track):
                rendered = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                layer = thunder_breaker.engine.base.clean_rgba(
                    thunder_breaker.engine.base.decode_source_canvas(canvas)
                )
                origin_x, origin_y = thunder_breaker.engine.base.canvas_origin(canvas, meta)
                rendered.alpha_composite(layer, (WIDTH // 2 - origin_x, HEIGHT // 2 - origin_y))
                layer.close()
                rgb = rendered.convert("RGB")
                alpha_channel = rendered.getchannel("A")
                color.stdin.write(rgb.tobytes())
                alpha.stdin.write(alpha_channel.tobytes())
                rgb.close()
                alpha_channel.close()
                rendered.close()
                if index == 0 or (index + 1) % 20 == 0 or index + 1 == len(track):
                    print(f"encoded god-of-sea-vi: {index + 1}/{len(track)}", flush=True)
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
    print(f"wrote: {output} frames={len(delays)} duration_ms={sum(delays)} bytes={output.stat().st_size}")
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
