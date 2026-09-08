#!/usr/bin/env python3
"""
生成物品图标图集：从 Item.wz 提取图标，生成图集 PNG 和 catalog.json
需要 wzpy 库来解码 canvas 数据
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import io
import math

ROOT = Path(__file__).resolve().parents[2]
WZPY_ROOT = ROOT / "tool" / "wz-python"
for dependency in (WZPY_ROOT,):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from wzpy import WzCanvasProperty, WzImage, WzKey
from wzpy.canvas import decode_canvas

SERVER_ITEM = ROOT / "gms-server" / "wz" / "Item.wz"
CLIENT_ITEM = ROOT / "clien" / "Data" / "Item"
ZH_STRING = ROOT / "gms-server" / "wz-zh-CN" / "String.wz"
OUTPUT_DIR = ROOT / "gms-server" / "src" / "main" / "resources" / "item-catalog"
ATLAS_DIR = OUTPUT_DIR / "atlases"

# 物品分类配置
CATEGORIES = {
    "Consume": {"label": "消耗物品", "string_file": "Consume.img", "prefixes": ["02"]},
    "Etc": {"label": "其他物品", "string_file": "Etc.img", "prefixes": ["04"], "sub_path": "Etc"},
    "Install": {"label": "设置物品", "string_file": "Ins.img", "prefixes": ["03"]},
    "Cash": {"label": "现金物品", "string_file": "Cash.img", "prefixes": ["05"]},
    "Pet": {"label": "宠物", "string_file": "Pet.img", "prefixes": ["0500"]},
    "Special": {"label": "特殊物品", "string_file": None, "prefixes": ["09"]},
}

CELL_SIZE = 48  # 图标格子大小
GMS_KEY = WzKey.for_region("GMS")


def load_string_names():
    """加载中文物品名称"""
    names = {}
    for cat_key, cat_info in CATEGORIES.items():
        string_file = cat_info.get("string_file")
        if not string_file:
            continue
        
        # 尝试加载中文字符串
        zh_path = ZH_STRING / string_file
        if not zh_path.exists():
            print(f"Warning: Chinese string file not found: {zh_path}")
            continue
        
        try:
            tree = ET.parse(zh_path)
            root = tree.getroot()
            
            # 根据分类解析不同的路径
            if cat_key == "Etc":
                # Etc.img 有子路径 Etc
                etc_node = root.find(".//imgdir[@name='Etc']")
                if etc_node is not None:
                    for item_node in etc_node.findall("imgdir"):
                        item_id = item_node.get("name")
                        name_node = item_node.find("string[@name='name']")
                        desc_node = item_node.find("string[@name='desc']")
                        names[item_id] = {
                            "name": name_node.get("value") if name_node is not None else "",
                            "desc": desc_node.get("value") if desc_node is not None else ""
                        }
            else:
                # 其他分类直接遍历
                for item_node in root.findall("imgdir"):
                    item_id = item_node.get("name")
                    name_node = item_node.find("string[@name='name']")
                    desc_node = item_node.find("string[@name='desc']")
                    names[item_id] = {
                        "name": name_node.get("value") if name_node is not None else "",
                        "desc": desc_node.get("value") if desc_node is not None else ""
                    }
        except Exception as e:
            print(f"Warning: Failed to parse {zh_path}: {e}")
    
    return names


def decode_icon_from_img(img_path, item_id):
    """从IMG文件解码图标"""
    try:
        wz_img = WzImage(str(img_path), GMS_KEY)
        wz_img.parse()
        
        # 查找物品节点
        item_node = wz_img.find_child(item_id)
        if item_node is None:
            return None
        
        # 查找info/icon节点
        info_node = item_node.find_child("info")
        if info_node is None:
            return None
        
        icon_node = info_node.find_child("icon")
        if icon_node is None:
            return None
        
        if isinstance(icon_node, WzCanvasProperty):
            # 解码canvas数据
            decoded = decode_canvas(icon_node)
            if decoded is not None:
                return decoded
        
        return None
    except Exception as e:
        print(f"Warning: Failed to decode icon from {img_path}: {e}")
        return None


def collect_items_with_icons():
    """收集所有物品信息和图标"""
    items = []
    string_names = load_string_names()
    
    for cat_key, cat_info in CATEGORIES.items():
        cat_dir = SERVER_ITEM / cat_key
        if not cat_dir.exists():
            print(f"Warning: Category directory not found: {cat_dir}")
            continue
        
        print(f"Processing category: {cat_key}")
        
        # 遍历该分类下的所有img文件
        for img_file in sorted(cat_dir.glob("*.img.xml")):
            img_name = img_file.stem.replace(".img", "")
            
            try:
                tree = ET.parse(img_file)
                root = tree.getroot()
                
                # 遍历所有物品节点
                for item_node in root.findall("imgdir"):
                    item_id = item_node.get("name")
                    if not item_id or not item_id.isdigit():
                        continue
                    
                    # 检查是否有icon
                    info_node = item_node.find("imgdir[@name='info']")
                    has_icon = False
                    specs = {}
                    icon_data = None
                    
                    if info_node is not None:
                        icon_node = info_node.find("canvas[@name='icon']")
                        has_icon = icon_node is not None
                        
                        # 提取基本信息
                        price_node = info_node.find("int[@name='price']")
                        if price_node is not None:
                            specs["price"] = int(price_node.get("value", 0))
                        
                        slot_max_node = info_node.find("int[@name='slotMax']")
                        if slot_max_node is not None:
                            specs["slotMax"] = int(slot_max_node.get("value", 0))
                    
                    # 提取spec信息（消耗品的hp/mp恢复等）
                    spec_node = item_node.find("imgdir[@name='spec']")
                    if spec_node is not None:
                        for spec_child in spec_node:
                            if spec_child.tag == "int":
                                specs[spec_child.get("name")] = int(spec_child.get("value", 0))
                    
                    # 获取名称
                    name_info = string_names.get(item_id, {})
                    name = name_info.get("name", "")
                    desc = name_info.get("desc", "")
                    
                    # 如果没有中文名，使用默认名
                    if not name:
                        name = f"Item {item_id}"
                    
                    # 尝试从客户端IMG解码图标
                    if has_icon:
                        client_img_path = CLIENT_ITEM / cat_key / f"{img_name}.img"
                        if client_img_path.exists():
                            icon_data = decode_icon_from_img(client_img_path, item_id)
                    
                    items.append({
                        "id": int(item_id),
                        "name": name,
                        "desc": desc,
                        "category": cat_key,
                        "specs": specs,
                        "has_icon": has_icon,
                        "icon_data": icon_data
                    })
            except Exception as e:
                print(f"Warning: Failed to parse {img_file}: {e}")
    
    return items


def create_atlases(items, cell_size=CELL_SIZE):
    """创建图集"""
    # 按分类分组
    category_items = {}
    for item in items:
        cat = item["category"]
        if cat not in category_items:
            category_items[cat] = []
        category_items[cat].append(item)
    
    atlases = {}
    
    for cat_key, cat_items in category_items.items():
        # 过滤有图标的物品
        items_with_icons = [item for item in cat_items if item["icon_data"] is not None]
        
        if not items_with_icons:
            print(f"No items with icons in category {cat_key}")
            atlases[cat_key] = {"count": len(cat_items), "icons": 0, "width": 0, "height": 0}
            continue
        
        # 计算图集尺寸
        count = len(items_with_icons)
        cols = min(count, 64)  # 每行最多64个
        rows = math.ceil(count / cols)
        
        width = cols * cell_size
        height = rows * cell_size
        
        # 创建图集图像
        atlas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # 填充图标
        for idx, item in enumerate(items_with_icons):
            row = idx // cols
            col = idx % cols
            x = col * cell_size
            y = row * cell_size
            
            icon = item["icon_data"]
            if icon:
                # 调整图标大小
                icon = icon.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
                atlas.paste(icon, (x, y))
                
                # 记录坐标
                item["x"] = x
                item["y"] = y
            else:
                item["x"] = 0
                item["y"] = 0
        
        # 保存图集
        atlas_path = ATLAS_DIR / f"{cat_key}.png"
        atlas.save(str(atlas_path))
        print(f"Saved atlas {cat_key}: {count} icons, {width}x{height}")
        
        atlases[cat_key] = {
            "count": len(cat_items),
            "icons": count,
            "width": width,
            "height": height
        }
    
    return atlases


def main():
    print("Generating item atlases...")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 收集物品信息和图标
    items = collect_items_with_icons()
    print(f"Found {len(items)} items total")
    
    # 统计各分类数量
    category_counts = {}
    items_with_icons_count = 0
    for item in items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if item["icon_data"] is not None:
            items_with_icons_count += 1
    
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count} items")
    
    print(f"Items with decoded icons: {items_with_icons_count}")
    
    # 创建图集
    atlases = create_atlases(items)
    
    # 生成catalog.json
    catalog = {
        "version": 1,
        "cellSize": CELL_SIZE,
        "atlases": atlases,
        "categories": [{"key": k, "count": category_counts.get(k, 0)} for k in CATEGORIES.keys()],
        "items": []
    }
    
    for item in items:
        catalog["items"].append({
            "id": item["id"],
            "name": item["name"],
            "desc": item["desc"],
            "category": item["category"],
            "specs": item["specs"],
            "icon": item["has_icon"],
            "x": item.get("x", 0),
            "y": item.get("y", 0)
        })
    
    # 保存catalog.json
    catalog_path = OUTPUT_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    
    print(f"Saved catalog to {catalog_path}")
    print(f"Total items: {len(items)}")
    print(f"Items with icons: {items_with_icons_count}")


if __name__ == "__main__":
    main()
