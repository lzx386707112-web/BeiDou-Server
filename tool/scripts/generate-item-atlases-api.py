#!/usr/bin/env python3
"""
使用 maplestory.io API 生成物品图标图集
不依赖 wzpy 库，直接从 API 下载图标
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
import io
import math
import requests
import time

ROOT = Path(__file__).resolve().parents[2]
SERVER_ITEM = ROOT / "gms-server" / "wz" / "Item.wz"
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
API_BASE = "https://maplestory.io/api/GMS/83/item"
MAX_ITEMS_PER_CATEGORY = 100  # 每个分类最多处理的物品数量（测试用）


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


def download_icon(item_id):
    """从 maplestory.io API 下载图标"""
    url = f"{API_BASE}/{item_id}/icon"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content)).convert('RGBA')
        else:
            return None
    except Exception as e:
        print(f"Warning: Failed to download icon for {item_id}: {e}")
        return None


def collect_items():
    """收集所有物品信息"""
    items = []
    string_names = load_string_names()
    
    for cat_key, cat_info in CATEGORIES.items():
        cat_dir = SERVER_ITEM / cat_key
        if not cat_dir.exists():
            print(f"Warning: Category directory not found: {cat_dir}")
            continue
        
        print(f"Processing category: {cat_key}")
        
        # 遍历该分类下的所有img文件
        for img_file in sorted(cat_dir.glob("*.img.xml"))[:10]:  # 测试：只处理前10个文件
            img_name = img_file.stem.replace(".img", "")
            
            try:
                tree = ET.parse(img_file)
                root = tree.getroot()
                
                # 遍历所有物品节点
                for item_node in root.findall("imgdir")[:10]:  # 测试：每个文件只处理前10个物品
                    item_id = item_node.get("name")
                    if not item_id or not item_id.isdigit():
                        continue
                    
                    # 检查是否有icon
                    info_node = item_node.find("imgdir[@name='info']")
                    has_icon = False
                    specs = {}
                    
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
                    
                    items.append({
                        "id": int(item_id),
                        "name": name,
                        "desc": desc,
                        "category": cat_key,
                        "specs": specs,
                        "has_icon": has_icon
                    })
                    
                    # 限制每个分类的物品数量
                    if len([i for i in items if i["category"] == cat_key]) >= MAX_ITEMS_PER_CATEGORY:
                        break
                
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
        print(f"\nCreating atlas for {cat_key}...")
        
        # 限制每个分类的物品数量
        items_to_process = cat_items[:MAX_ITEMS_PER_CATEGORY]
        
        # 下载图标
        icons = []
        for idx, item in enumerate(items_to_process):
            print(f"  Downloading icon {idx+1}/{len(items_to_process)}: {item['id']}", end="")
            icon = download_icon(item["id"])
            if icon:
                icons.append((item, icon))
                print(" ✓")
            else:
                print(" ✗")
            
            # 避免请求过快
            if idx % 10 == 9:
                time.sleep(1)
        
        if not icons:
            print(f"  No icons downloaded for {cat_key}")
            atlases[cat_key] = {"count": len(cat_items), "icons": 0, "width": 0, "height": 0}
            continue
        
        # 计算图集尺寸
        count = len(icons)
        cols = min(count, 16)  # 每行最多16个
        rows = math.ceil(count / cols)
        
        width = cols * cell_size
        height = rows * cell_size
        
        # 创建图集图像
        atlas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        
        # 填充图标
        for idx, (item, icon) in enumerate(icons):
            row = idx // cols
            col = idx % cols
            x = col * cell_size
            y = row * cell_size
            
            # 调整图标大小
            icon = icon.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
            atlas.paste(icon, (x, y))
            
            # 记录坐标
            item["x"] = x
            item["y"] = y
            item["has_icon"] = True
        
        # 保存图集
        atlas_path = ATLAS_DIR / f"{cat_key}.png"
        atlas.save(str(atlas_path))
        print(f"  Saved atlas {cat_key}: {count} icons, {width}x{height}")
        
        atlases[cat_key] = {
            "count": len(cat_items),
            "icons": count,
            "width": width,
            "height": height
        }
    
    return atlases


def main():
    print("Generating item atlases using maplestory.io API...")
    print(f"Max items per category: {MAX_ITEMS_PER_CATEGORY}")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 收集物品信息
    items = collect_items()
    print(f"\nFound {len(items)} items total")
    
    # 统计各分类数量
    category_counts = {}
    for item in items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count} items")
    
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
            "icon": item.get("has_icon", False),
            "x": item.get("x", 0),
            "y": item.get("y", 0)
        })
    
    # 保存catalog.json
    catalog_path = OUTPUT_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    
    print(f"\nSaved catalog to {catalog_path}")
    print(f"Total items: {len(items)}")
    print(f"Items with icons: {sum(1 for item in items if item.get('has_icon'))}")


if __name__ == "__main__":
    main()
