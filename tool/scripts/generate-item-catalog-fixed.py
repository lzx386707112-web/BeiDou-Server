#!/usr/bin/env python3
"""
生成物品预览目录：从 Item.wz 提取物品信息，生成 catalog.json
修复了中文名称加载的ID格式问题
"""

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER_ITEM = ROOT / "gms-server" / "wz" / "Item.wz"
ZH_STRING = ROOT / "gms-server" / "wz-zh-CN" / "String.wz"
OUTPUT_DIR = ROOT / "gms-server" / "src" / "main" / "resources" / "item-catalog"

# 物品分类配置
CATEGORIES = {
    "Consume": {"label": "消耗物品", "string_file": "Consume.img"},
    "Etc": {"label": "其他物品", "string_file": "Etc.img", "sub_path": "Etc"},
    "Install": {"label": "设置物品", "string_file": "Ins.img"},
    "Cash": {"label": "现金物品", "string_file": "Cash.img"},
    "Pet": {"label": "宠物", "string_file": "Pet.img"},
    "Special": {"label": "特殊物品", "string_file": None},
}

CELL_SIZE = 48


def load_string_names():
    """加载中文物品名称"""
    names = {}
    for cat_key, cat_info in CATEGORIES.items():
        string_file = cat_info.get("string_file")
        if not string_file:
            continue

        # 尝试加载中文字符串
        zh_path = ZH_STRING / f"{string_file}.xml"
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


def collect_items():
    """收集所有物品信息"""
    items = []
    string_names = load_string_names()
    print(f"Loaded {len(string_names)} item names from string files")

    for cat_key, cat_info in CATEGORIES.items():
        cat_dir = SERVER_ITEM / cat_key
        if not cat_dir.exists():
            print(f"Warning: Category directory not found: {cat_dir}")
            continue

        print(f"Processing category: {cat_key}")
        category_count = 0

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

                    # 获取名称 - 尝试不同的ID格式
                    # 物品WZ中的ID可能是 02000000 格式，字符串文件中是 2000000 格式
                    name_info = string_names.get(item_id, {})
                    if not name_info:
                        # 尝试去掉前导0
                        item_id_no_leading_zero = item_id.lstrip("0") or "0"
                        name_info = string_names.get(item_id_no_leading_zero, {})

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
                    category_count += 1

            except Exception as e:
                print(f"Warning: Failed to parse {img_file}: {e}")

        print(f"  {cat_key}: {category_count} items")

    return items


def main():
    print("Generating item catalog...")

    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 收集物品信息
    items = collect_items()
    print(f"\nFound {len(items)} items total")

    # 统计各分类数量
    category_counts = {}
    for item in items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 生成catalog.json
    catalog = {
        "version": 1,
        "cellSize": CELL_SIZE,
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
            "x": 0,
            "y": 0
        })

    # 保存catalog.json
    catalog_path = OUTPUT_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Saved catalog to {catalog_path}")
    print(f"Total items: {len(items)}")

    # 显示一些示例
    print("\nSample items:")
    for item in items[:5]:
        print(f"  {item['id']}: {item['name']} ({item['category']})")


if __name__ == "__main__":
    main()
