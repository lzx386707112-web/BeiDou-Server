#!/usr/bin/env python3
"""
使用 wzpy 生成怪物图标图集
从 Mob.wz 提取图标，生成图集 PNG 和 catalog.json
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import math

ROOT = Path(__file__).resolve().parents[2]
WZPY_ROOT = ROOT / "tool" / "wz-python"
for dependency in (WZPY_ROOT,):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from wzpy import WzImage, WzKey
from wzpy.canvas import decode_canvas

CLIENT_MOB = ROOT / "clien" / "Data" / "Mob"
ZH_STRING = ROOT / "gms-server" / "wz-zh-CN" / "String.wz"
OUTPUT_DIR = ROOT / "gms-server" / "src" / "main" / "resources" / "mob-catalog"
ATLAS_DIR = OUTPUT_DIR / "atlases"

CELL_SIZE = 96  # 怪物图标较大
GMS_KEY = WzKey.for_region("GMS")


def load_mob_names():
    """加载怪物中文名称"""
    names = {}
    zh_path = ZH_STRING / "Mob.img.xml"
    if not zh_path.exists():
        print(f"Warning: Mob string file not found: {zh_path}")
        return names

    try:
        tree = ET.parse(zh_path)
        root = tree.getroot()

        for item_node in root.findall("imgdir"):
            mob_id = item_node.get("name")
            name_node = item_node.find("string[@name='name']")
            if name_node is not None:
                names[mob_id] = name_node.get("value", "")
    except Exception as e:
        print(f"Warning: Failed to parse {zh_path}: {e}")

    return names


def decode_icon_from_img(img_path):
    """从IMG文件解码图标（尝试多个节点）"""
    try:
        img = WzImage.from_file(str(img_path), key=GMS_KEY)
        root = img.parse()

        # 尝试的节点顺序：move/0, stand/0, fly/0, regen/0
        node_paths = [
            ('move', '0'),
            ('stand', '0'),
            ('fly', '0'),
            ('regen', '0'),
        ]

        for parent_name, child_name in node_paths:
            parent_node = root.child(parent_name)
            if parent_node:
                icon_node = parent_node.child(child_name)
                if icon_node:
                    try:
                        decoded = decode_canvas(icon_node)
                        if decoded:
                            return decoded
                    except Exception:
                        continue
    except Exception as e:
        pass
    return None


def collect_mobs_with_icons():
    """收集所有怪物信息和图标"""
    mobs = []
    mob_names = load_mob_names()
    print(f"Loaded {len(mob_names)} mob names from string files")

    print(f"\nProcessing mobs...")
    mob_count = 0
    icons_decoded = 0

    # 遍历所有怪物IMG文件
    for img_file in sorted(CLIENT_MOB.glob("*.img")):
        mob_id = img_file.stem
        if not mob_id.isdigit():
            continue

        try:
            wz_img = WzImage.from_file(str(img_file), key=GMS_KEY)
            root = wz_img.parse()

            # 提取怪物属性
            stats = {}
            info_node = root.child('info')
            if info_node:
                for stat_name in ['level', 'exp', 'maxHP', 'maxMP', 'PADamage', 'PDDamage',
                                  'MADamage', 'MDDamage', 'acc', 'eva', 'speed']:
                    stat_node = info_node.child(stat_name)
                    if stat_node and stat_node.value is not None:
                        try:
                            stats[stat_name] = int(stat_node.value)
                        except (ValueError, TypeError):
                            pass

            # 提取图标
            icon_data = decode_icon_from_img(img_file)
            has_icon = icon_data is not None
            if has_icon:
                icons_decoded += 1

            # 获取名称
            name = mob_names.get(mob_id, "")
            if not name:
                # 尝试去掉前导0
                mob_id_no_leading_zero = mob_id.lstrip("0") or "0"
                name = mob_names.get(mob_id_no_leading_zero, "")
            if not name:
                name = f"Mob {mob_id}"

            mobs.append({
                "id": int(mob_id),
                "name": name,
                "stats": stats,
                "has_icon": has_icon,
                "icon_data": icon_data
            })
            mob_count += 1

            if mob_count % 100 == 0:
                print(f"  Processed {mob_count} mobs...")

        except Exception as e:
            print(f"Warning: Failed to parse {img_file}: {e}")

    print(f"  Total: {mob_count} mobs, {icons_decoded} icons decoded")
    return mobs


def create_atlas(mobs, cell_size=CELL_SIZE):
    """创建图集"""
    mobs_with_icons = [mob for mob in mobs if mob["icon_data"] is not None]

    if not mobs_with_icons:
        print("No mobs with icons")
        return {"count": len(mobs), "icons": 0, "width": 0, "height": 0}

    # 计算图集尺寸
    count = len(mobs_with_icons)
    cols = min(count, 32)  # 每行最多32个
    rows = math.ceil(count / cols)

    width = cols * cell_size
    height = rows * cell_size

    # 创建图集图像
    atlas = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # 填充图标
    for idx, mob in enumerate(mobs_with_icons):
        row = idx // cols
        col = idx % cols
        x = col * cell_size
        y = row * cell_size

        icon = mob["icon_data"]
        if icon:
            # 调整图标大小，保持比例
            icon_w, icon_h = icon.size
            scale = min(cell_size / icon_w, cell_size / icon_h)
            new_w = int(icon_w * scale)
            new_h = int(icon_h * scale)
            icon = icon.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # 居中粘贴
            paste_x = x + (cell_size - new_w) // 2
            paste_y = y + (cell_size - new_h) // 2
            atlas.paste(icon, (paste_x, paste_y))

            # 记录坐标
            mob["x"] = x
            mob["y"] = y
        else:
            mob["x"] = 0
            mob["y"] = 0

    # 保存图集
    atlas_path = ATLAS_DIR / "mob.png"
    atlas.save(str(atlas_path))
    print(f"Saved atlas: {count} icons, {width}x{height}")

    return {
        "count": len(mobs),
        "icons": count,
        "width": width,
        "height": height
    }


def main():
    print("Generating mob atlases using wzpy...")

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)

    # 收集怪物信息和图标
    mobs = collect_mobs_with_icons()
    print(f"\nFound {len(mobs)} mobs total")

    # 创建图集
    atlas_info = create_atlas(mobs)

    # 生成catalog.json
    catalog = {
        "version": 1,
        "cellSize": CELL_SIZE,
        "atlas": atlas_info,
        "mobs": []
    }

    for mob in mobs:
        catalog["mobs"].append({
            "id": mob["id"],
            "name": mob["name"],
            "stats": mob["stats"],
            "icon": mob["has_icon"],
            "x": mob.get("x", 0),
            "y": mob.get("y", 0)
        })

    # 保存catalog.json
    catalog_path = OUTPUT_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"\nSaved catalog to {catalog_path}")
    print(f"Total mobs: {len(mobs)}")
    print(f"Mobs with icons: {atlas_info['icons']}")


if __name__ == "__main__":
    main()
