#!/usr/bin/env python3
"""
扫描所有可能引用怪物ID的数据源，找出没有被任何地方引用的怪物。
数据源：
1. Map.wz 地图刷怪 (mob spawn)
2. Mob.wz 怪物间引用 (revive/summon)
3. Reactor.wz 反应堆召唤
4. Item.wz 掉落表
5. Quest.wz 任务要求
6. Java 服务端代码 (硬编码ID)
7. NPC/任务脚本 (scripts-zh-CN)
8. Skill.wz 技能召唤
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/lizixian/Documents/mxd/BeiDou-Server")
WZ = ROOT / "gms-server" / "wz"
WZ_ZH = ROOT / "gms-server" / "wz-zh-CN"
MOB_DIR = ROOT / "clien" / "Data" / "Mob"

# All mob IDs from client IMG files
all_mob_ids = set()
for f in MOB_DIR.glob("*.img"):
    try:
        mob_id = int(f.stem)
        all_mob_ids.add(mob_id)
    except ValueError:
        pass

print(f"Total mob IMG files: {len(all_mob_ids)}")

# Track references: mob_id -> set of source descriptions
references = defaultdict(set)

def extract_mob_ids_from_file(filepath, source_label):
    """Extract 7-digit numbers that look like mob IDs from an XML file."""
    try:
        text = filepath.read_text(encoding='utf-8', errors='ignore')
    except:
        return
    
    # Match patterns like: name="id" value="1234567" or value="1234567"
    # Also match: <int name="0" value="1234567"/> (revive entries)
    for m in re.finditer(r'value="(\d{7})"', text):
        val = int(m.group(1))
        if val in all_mob_ids:
            references[val].add(source_label)

def scan_directory_xml(directory, source_label, glob_pattern="*.xml"):
    """Scan all XML files in a directory for mob ID references."""
    if not directory.exists():
        return
    count = 0
    for xml_file in directory.rglob(glob_pattern):
        extract_mob_ids_from_file(xml_file, source_label)
        count += 1
    print(f"  Scanned {count} files in {source_label}")

def scan_js_scripts(directory, source_label):
    """Scan JS scripts for numeric literals that match mob IDs."""
    if not directory.exists():
        return
    count = 0
    for js_file in directory.rglob("*.js"):
        try:
            text = js_file.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        # Look for 7-digit numbers in various contexts
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mob_ids:
                references[val].add(f"{source_label}:{js_file.name}")
        count += 1
    print(f"  Scanned {count} JS files in {source_label}")

def scan_java_code(directory, source_label):
    """Scan Java source for hardcoded mob IDs."""
    if not directory.exists():
        return
    count = 0
    for java_file in directory.rglob("*.java"):
        try:
            text = java_file.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mob_ids:
                references[val].add(f"{source_label}:{java_file.name}")
        count += 1
    print(f"  Scanned {count} Java files in {source_label}")

# === Scan all sources ===

print("\n1. Scanning Map.wz (mob spawns)...")
scan_directory_xml(WZ / "Map.wz", "Map.wz")
if (WZ_ZH / "Map.wz").exists():
    scan_directory_xml(WZ_ZH / "Map.wz", "Map.wz-zh")

print("\n2. Scanning Mob.wz (inter-mob refs: revive/summon)...")
scan_directory_xml(WZ / "Mob.wz", "Mob.wz")
if (WZ_ZH / "Mob.wz").exists():
    scan_directory_xml(WZ_ZH / "Mob.wz", "Mob.wz-zh")

print("\n3. Scanning Reactor.wz (mob spawns from reactors)...")
scan_directory_xml(WZ / "Reactor.wz", "Reactor.wz")
if (WZ_ZH / "Reactor.wz").exists():
    scan_directory_xml(WZ_ZH / "Reactor.wz", "Reactor.wz-zh")

print("\n4. Scanning Item.wz (drop tables)...")
scan_directory_xml(WZ / "Item.wz", "Item.wz")
if (WZ_ZH / "Item.wz").exists():
    scan_directory_xml(WZ_ZH / "Item.wz", "Item.wz-zh")

print("\n5. Scanning Quest.wz (quest mob requirements)...")
scan_directory_xml(WZ / "Quest.wz", "Quest.wz")
if (WZ_ZH / "Quest.wz").exists():
    scan_directory_xml(WZ_ZH / "Quest.wz", "Quest.wz-zh")

print("\n6. Scanning Skill.wz (skill summons)...")
scan_directory_xml(WZ / "Skill.wz", "Skill.wz")

print("\n7. Scanning String.wz (mob names)...")
scan_directory_xml(WZ / "String.wz", "String.wz")
if (WZ_ZH / "String.wz").exists():
    scan_directory_xml(WZ_ZH / "String.wz", "String.wz-zh")

print("\n8. Scanning NPC scripts (scripts-zh-CN)...")
scan_js_scripts(ROOT / "scripts-zh-CN", "scripts-zh-CN")

print("\n9. Scanning Java server code...")
scan_java_code(ROOT / "gms-server" / "src", "java-src")

print("\n10. Scanning mob-catalog.json...")
import json
cat_path = ROOT / "gms-server" / "src" / "main" / "resources" / "mob-catalog" / "catalog.json"
if cat_path.exists():
    with open(cat_path) as f:
        cat = json.load(f)
    for mob in cat.get("mobs", []):
        mid = mob.get("id")
        if mid and mid in all_mob_ids:
            references[mid].add("mob-catalog")

# === Analysis ===
print("\n" + "="*60)
referenced_ids = set(references.keys())
unreferenced_ids = all_mob_ids - referenced_ids

print(f"\nTotal mobs: {len(all_mob_ids)}")
print(f"Referenced: {len(referenced_ids)}")
print(f"UNREFERENCED: {len(unreferenced_ids)}")

# Get file sizes for unreferenced mobs
unreferenced_with_size = []
for mid in unreferenced_ids:
    fpath = MOB_DIR / f"{mid}.img"
    if fpath.exists():
        size = fpath.stat().st_size
        unreferenced_with_size.append((mid, size))

unreferenced_with_size.sort(key=lambda x: -x[1])

total_unref_size = sum(s for _, s in unreferenced_with_size)
print(f"Total unreferenced mob size: {total_unref_size/1024/1024:.1f} MB")

# Show top unreferenced by size
print(f"\n{'='*60}")
print(f"UNREFERENCED MOBS (sorted by size, top100):")
print(f"{'='*60}")
print(f"{'Rank':<6}{'MobID':<12}{'Size':>10}{'Source Check'}")
print(f"{'-'*6}{'-'*12}{'-'*10}{'-'*30}")

for i, (mid, size) in enumerate(unreferenced_with_size[:100], 1):
    size_str = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
    # Quick check: is it in mob-catalog?
    in_cat = "catalog" if mid in {m.get("id") for m in cat.get("mobs", [])} else ""
    print(f"{i:<6}{mid:<12}{size_str:>10}  {in_cat}")

# Also show by reference source distribution
print(f"\n{'='*60}")
print(f"REFERENCE SOURCE DISTRIBUTION:")
print(f"{'='*60}")
source_counts = defaultdict(int)
for mid, sources in references.items():
    for src in sources:
        # Normalize source name
        base = src.split(":")[0] if ":" in src else src
        source_counts[base] += 1

for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
    print(f"  {src}: {cnt} mobs")

# Save full list to file
output_path = ROOT / "docs" / "unreferenced-mobs.txt"
with open(output_path, 'w') as f:
    f.write(f"Unreferenced Mobs Analysis\n")
    f.write(f"Total: {len(unreferenced_with_size)} mobs, {total_unref_size/1024/1024:.1f} MB\n")
    f.write(f"{'='*60}\n\n")
    for i, (mid, size) in enumerate(unreferenced_with_size, 1):
        size_str = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
        f.write(f"{i:>4}. {mid}  ({size_str})\n")
print(f"\nFull list saved to: {output_path}")
