#!/usr/bin/env python3
"""
全面扫描所有引用源，找出未被引用的怪物。
修复V1版的bug：Map.wz中string类型的id值被漏掉。
"""
import re, json
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/lizixian/Documents/mxd/BeiDou-Server")
WZ = ROOT / "gms-server" / "wz"
WZ_ZH = ROOT / "gms-server" / "wz-zh-CN"
MOB_DIR = ROOT / "clien" / "Data" / "Mob"

# === Step1: 收集所有怪物ID ===
all_mobs = set()
for f in MOB_DIR.glob("*.img"):
    try:
        all_mobs.add(int(f.stem))
    except:
        pass
print(f"[1] 怪物IMG文件: {len(all_mobs)}")

# === 辅助函数 ===
def scan_xml_for_mob_ids(directory, label, context_filter=None):
    """
    从XML文件中提取7位数字中属于怪物ID的那些。
    context_filter: 可选的上下文过滤函数 (line_text) -> bool
    """
    refs = set()
    if not directory.exists():
        print(f"  {label}: 目录不存在")
        return refs
    count = 0
    for f in directory.rglob("*.xml"):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        count += 1
        # 提取所有7位数字
        for m in re.finditer(r'value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs:
                if context_filter is None:
                    refs.add(val)
                else:
                    # 检查上下文
                    line_start = text.rfind('\n', 0, m.start()) + 1
                    line_end = text.find('\n', m.end())
                    line = text[line_start:line_end] if line_end > 0 else text[line_start:]
                    if context_filter(line):
                        refs.add(val)
    print(f"  {label}: {count}个文件, {len(refs)}个怪物ID")
    return refs

def scan_xml_for_mob_ids_in_map_spawns(directory, label):
    """专门扫描地图刷怪数据——找type="m"后面的id值"""
    refs = set()
    if not directory.exists():
        print(f"  {label}: 目录不存在")
        return refs
    count = 0
    for f in directory.rglob("*.xml"):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        count += 1
        # 方法1: type="m"上下文中的id (int或string类型)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'name="type"' and 'value="m"' in line:
                for j in range(i+1, min(i+5, len(lines))):
                    m = re.search(r'name="id"\s+value="(\d+)"', lines[j])
                    if m:
                        val = int(m.group(1))
                        if val in all_mobs:
                            refs.add(val)
                        break
        # 方法2: 所有string id值中的怪物ID (覆盖非type="m"但仍是怪物的情况)
        for m in re.finditer(r'<string name="id"\s+value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs:
                refs.add(val)
        # 方法3: 所有int id值中的怪物ID
        for m in re.finditer(r'<int name="id"\s+value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs:
                refs.add(val)
    print(f"  {label}: {count}个文件, {len(refs)}个怪物ID")
    return refs

def scan_js_scripts(directory, label):
    """扫描JS脚本中的怪物ID引用"""
    refs = set()
    if not directory.exists():
        print(f"  {label}: 目录不存在")
        return refs
    count = 0
    for f in directory.rglob("*.js"):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        count += 1
        # 7位数字，带单词边界
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mobs:
                refs.add(val)
    print(f"  {label}: {count}个文件, {len(refs)}个怪物ID")
    return refs

def scan_java_code(directory, label):
    """扫描Java代码中的怪物ID引用"""
    refs = set()
    if not directory.exists():
        print(f"  {label}: 目录不存在")
        return refs
    count = 0
    for f in directory.rglob("*.java"):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        count += 1
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mobs:
                refs.add(val)
    print(f"  {label}: {count}个文件, {len(refs)}个怪物ID")
    return refs

# === Step2: 扫描所有引用源 ===
print("\n=== 扫描引用源 ===")

# 1. Map.wz - 地图刷怪 (最全面的扫描)
print("\n[Map.wz] 刷怪数据:")
map_refs = scan_xml_for_mob_ids_in_map_spawns(WZ / "Map.wz", "Map.wz")

# 2. Mob.wz - 怪物间引用 (revive/summon/boss等)
print("\n[Mob.wz] 怪物间引用:")
mob_refs = scan_xml_for_mob_ids(WZ / "Mob.wz", "Mob.wz (全部)")

# 3. Reactor.wz - 反应堆
print("\n[Reactor.wz]:")
reactor_refs = scan_xml_for_mob_ids(WZ / "Reactor.wz", "Reactor.wz")

# 4. Item.wz - 掉落表
print("\n[Item.wz] 掉落表:")
item_refs = scan_xml_for_mob_ids(WZ / "Item.wz", "Item.wz (全部)")

# 5. Quest.wz - 任务
print("\n[Quest.wz]:")
quest_refs = scan_xml_for_mob_ids(WZ / "Quest.wz", "Quest.wz (全部)")

# 6. Skill.wz - 技能
print("\n[Skill.wz]:")
skill_refs = scan_xml_for_mob_ids(WZ / "Skill.wz", "Skill.wz (全部)")

# 7. String.wz - 怪物名
print("\n[String.wz] 怪物名定义:")
def scan_string_mobs(directory, label):
    refs = set()
    if not directory.exists():
        print(f"  {label}: 目录不存在")
        return refs
    count = 0
    for f in directory.rglob("*.xml"):
        if 'mob' not in f.name.lower() and 'Mob' not in f.name:
            continue
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
        except:
            continue
        count += 1
        for m in re.finditer(r'<imgdir name="(\d+)">', text):
            val = int(m.group(1))
            if val in all_mobs:
                refs.add(val)
    print(f"  {label}: {count}个文件, {len(refs)}个怪物ID")
    return refs

string_refs = scan_string_mobs(WZ / "String.wz", "String.wz")

# 8. wz-zh-CN
print("\n[wz-zh-CN]:")
zh_refs = set()
for subdir in WZ_ZH.glob("*.wz"):
    if subdir.is_dir():
        if 'String' in subdir.name:
            zh_refs |= scan_string_mobs(subdir, f"wz-zh-CN/{subdir.name}")
        else:
            zh_refs |= scan_xml_for_mob_ids(subdir, f"wz-zh-CN/{subdir.name}")

# 9. NPC/任务脚本
print("\n[scripts]:")
scripts_dir = ROOT / "gms-server" / "scripts-zh-CN"
script_refs = scan_js_scripts(scripts_dir, "scripts-zh-CN")

# 10. Java服务端代码
print("\n[Java代码]:")
java_refs = scan_java_code(ROOT / "gms-server" / "src", "java-src")

# 11. mob-catalog.json
print("\n[mob-catalog]:")
cat_path = ROOT / "gms-server" / "src" / "main" / "resources" / "mob-catalog" / "catalog.json"
cat_refs = set()
if cat_path.exists():
    with open(cat_path) as f:
        cat = json.load(f)
    for mob in cat.get("mobs", []):
        mid = mob.get("id")
        if mid and mid in all_mobs:
            cat_refs.add(mid)
    print(f"  catalog: {len(cat_refs)}个怪物ID")

# === Step3: 合并所有引用 ===
print("\n" + "="*60)
all_refs = map_refs | mob_refs | reactor_refs | item_refs | quest_refs | skill_refs | string_refs | zh_refs | script_refs | java_refs | cat_refs
referenced = all_refs & all_mobs
unreferenced = all_mobs - referenced

print(f"引用源统计:")
print(f"  Map.wz刷怪:      {len(map_refs & all_mobs):>5}")
print(f"  Mob.wz互引:      {len(mob_refs & all_mobs):>5}")
print(f"  Reactor.wz:      {len(reactor_refs & all_mobs):>5}")
print(f"  Item.wz掉落:     {len(item_refs & all_mobs):>5}")
print(f"  Quest.wz任务:    {len(quest_refs & all_mobs):>5}")
print(f"  Skill.wz技能:    {len(skill_refs & all_mobs):>5}")
print(f"  String.wz名字:   {len(string_refs & all_mobs):>5}")
print(f"  wz-zh-CN中文:    {len(zh_refs & all_mobs):>5}")
print(f"  脚本引用:        {len(script_refs & all_mobs):>5}")
print(f"  Java代码:        {len(java_refs & all_mobs):>5}")
print(f"  mob-catalog:     {len(cat_refs):>5}")
print(f"  {'─'*30}")
print(f"  总计引用:        {len(referenced):>5}")
print(f"  总计怪物:        {len(all_mobs):>5}")
print(f"  未引用:          {len(unreferenced):>5}")

# === Step4: 未引用怪物详情 ===
unref_sizes = []
for mid in unreferenced:
    fpath = MOB_DIR / f"{mid}.img"
    if fpath.exists():
        unref_sizes.append((mid, fpath.stat().st_size))
unref_sizes.sort(key=lambda x: -x[1])

total_unref = sum(s for _, s in unref_sizes)
total_all = sum(f.stat().st_size for f in MOB_DIR.glob("*.img"))
print(f"\n未引用怪物大小: {total_unref/1024/1024:.1f} MB / {total_all/1024/1024:.1f} MB ({total_unref/total_all*100:.1f}%)")

# 分类
categories = defaultdict(list)
for mid, size in unref_sizes:
    prefix = str(mid)[:2]
    categories[prefix].append((mid, size))

print(f"\n按ID前缀分类:")
print(f"{'前缀':<10}{'数量':<8}{'大小':>10}{'示例'}")
print(f"{'─'*60}")
for prefix in sorted(categories.keys()):
    items = categories[prefix]
    total = sum(s for _, s in items)
    examples = ', '.join(str(m) for m, _ in sorted(items)[:3])
    if len(items) > 3:
        examples += f' (+{len(items)-3})'
    sz = f"{total/1024/1024:.1f}M" if total >= 1024*1024 else f"{total/1024:.0f}K"
    print(f"{prefix}xxxxx   {len(items):<8}{sz:>10}  {examples}")

# Top100
print(f"\nTop100未引用怪物(按大小):")
print(f"{'排名':<6}{'怪物ID':<12}{'大小':>10}")
print(f"{'─'*28}")
for i, (mid, size) in enumerate(unref_sizes[:100], 1):
    sz = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
    print(f"{i:<6}{mid:<12}{sz:>10}")

# 保存完整列表
out = ROOT / "docs" / "unreferenced-mobs.txt"
with open(out, 'w') as f:
    f.write(f"未引用怪物列表 (V2全面扫描)\n")
    f.write(f"总计: {len(unref_sizes)}个, {total_unref/1024/1024:.1f}MB\n")
    f.write(f"{'='*60}\n\n")
    for i, (mid, size) in enumerate(unref_sizes, 1):
        sz = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
        f.write(f"{i:>4}. {mid}  ({sz})\n")
print(f"\n完整列表已保存: {out}")
