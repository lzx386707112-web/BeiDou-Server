#!/usr/bin/env python3
"""Render a contact sheet from the installed Shadower Dual Blade effects."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "tool/wz-python")]

from wzpy import WzImage, WzKey  # noqa: E402
from wzpy.canvas import decode_canvas  # noqa: E402
from wzpy.properties import WzCanvasProperty, WzSubProperty  # noqa: E402


OUTPUT = ROOT / "docs/patches/shadower-dual-blade-skills-preview.png"
SKILLS = (
    (4201004, "双刃旋"), (4201005, "分身斩"),
    (4211002, "跃空斩"), (4211004, "血雨暴风狂斩"),
    (4211006, "翔空落叶斩"), (4221001, "幻影箭"),
    (4221003, "闪光弹"), (4221004, "短剑升天"),
    (4221007, "短刀护佑"),
)


def load_font(size: int):
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def choose_canvas(node: WzSubProperty) -> WzCanvasProperty:
    canvases = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, WzCanvasProperty):
            with decode_canvas(current, region="GMS") as decoded:
                alpha = decoded.getchannel("A")
                bbox = alpha.getbbox()
                score = 0 if bbox is None else (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
            canvases.append((score, current))
        if hasattr(current, "children"):
            stack.extend(current.children())
    if not canvases:
        raise RuntimeError(f"no Canvas under {node.name}")
    return max(canvases, key=lambda item: item[0])[1]


def main() -> None:
    roots = {}
    for book in (420, 421, 422):
        path = ROOT / f"clien/Data/Skill/{book}.img"
        image = WzImage.from_bytes(
            path.read_bytes(), key=WzKey.for_region("GMS"), name=path.name
        )
        roots[book] = image.parse()
        if image.truncated or image.parse_warnings:
            raise RuntimeError(f"malformed {path}: {image.parse_warnings}")

    width, height = 1280, 980
    sheet = Image.new("RGBA", (width, height), (13, 16, 28, 255))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(36)
    label_font = load_font(22)
    small_font = load_font(16)
    draw.text((48, 30), "侠盗二至四转 · 双刀技能预览", font=title_font, fill=(245, 247, 255))
    draw.text((49, 78), "仅攻击技能取自 TMS v209；职业及二至四转辅助技能保持侠盗原版", font=small_font, fill=(153, 165, 194))

    cell_w, cell_h = 286, 260
    for index, (skill_id, name) in enumerate(SKILLS):
        row, col = divmod(index, 4)
        x, y = 48 + col * 302, 120 + row * 276
        draw.rounded_rectangle((x, y, x + cell_w, y + cell_h), radius=16,
                               fill=(24, 29, 48), outline=(61, 72, 110), width=2)
        carrier = roots[skill_id // 10000].get(f"dualBladeSkin/{skill_id}")
        frame = choose_canvas(carrier)
        with decode_canvas(frame, region="GMS") as decoded:
            effect = decoded.convert("RGBA")
        effect.thumbnail((250, 185), Image.Resampling.LANCZOS)
        px = x + (cell_w - effect.width) // 2
        py = y + 14 + (185 - effect.height) // 2
        sheet.alpha_composite(effect, (px, py))
        effect.close()
        draw.text((x + 16, y + 205), name, font=label_font, fill=(244, 245, 252))
        draw.text((x + 17, y + 235), str(skill_id), font=small_font, fill=(136, 151, 190))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(OUTPUT, quality=95)
    print(OUTPUT)


if __name__ == "__main__":
    main()
