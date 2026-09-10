#!/usr/bin/env python3
"""
V3精确版：用上下文过滤区分怪物ID和其他ID。
- Map.wz: 扫type="m" + string/int id值 (覆盖864xxxx的string格式)
- Mob.wz: 扫revive/summon上下文
- Item.wz: 扫name="mob"属性
- Quest.wz: 扫name="mob"属性
- Skill.wz: 扫name="mob"属性
- String.wz: 扫Mob.img的imgdir name
- 脚本/Java: 扫7位数字（有噪音但宁可多不可少）
"""
import re, json
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/lizixian/Documents/mxd/BeiDou-Server")
WZ = ROOT / "gms-server" / "wz"
WZ_ZH = ROOT / "gms-server" / "wz-zh-CN"
MOB_DIR = ROOT / "clien" / "Data" / "Mob"

all_mobs = set()
for f in MOB_DIR.glob("*.img"):
    try: all_mobs.add(int(f.stem))
    except: pass
print(f"怪物IMG文件: {len(all_mobs)}")

# ========== 各引用源精确扫描 ==========

def scan_map_spawns(directory):
    """Map.wz: type="m"中的id + 所有string/int id值"""
    refs = set()
    if not directory.exists(): return refs
    for f in directory.rglob("*.xml"):
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        lines = text.split('\n')
        # 方法1: type="m"上下文
        for i, line in enumerate(lines):
            if 'name="type"' and 'value="m"' in line:
                for j in range(i+1, min(i+5, len(lines))):
                    m = re.search(r'name="id"\s+value="(\d+)"', lines[j])
                    if m:
                        val = int(m.group(1))
                        if val in all_mobs: refs.add(val)
                        break
        # 方法2: string name="id" (覆盖864xxxx等string格式)
        for m in re.finditer(r'<string name="id"\s+value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
        # 方法3: int name="id"
        for m in re.finditer(r'<int name="id"\s+value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
    return refs

def scan_mob_revive_summon(directory):
    """Mob.wz: revive/summon/boss上下文中的怪物ID"""
    refs = set()
    if not directory.exists(): return refs
    for f in directory.rglob("*.xml"):
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        # 提取该文件的怪物ID（img文件名）
        try: own_id = int(f.stem)
        except: own_id = None
        # 扫描revive段
        in_section = False
        for line in text.split('\n'):
            if 'name="revive"' in line or 'name="summon"' in line:
                in_section = True
            elif '</imgdir>' in line and in_section:
                in_section = False
            elif in_section:
                m = re.search(r'value="(\d{7})"', line)
                if m:
                    val = int(m.group(1))
                    if val in all_mobs: refs.add(val)
        # 所有7位数值中的怪物ID（Mob.wz里的值大多是怪物引用）
        for m in re.finditer(r'value="(\d{7})"', text):
            val = int(m.group(1))
            if val in all_mobs and val != own_id:
                refs.add(val)
    return refs

def scan_mob_attr(directory, attr_name):
    """扫描name="<attr>"属性值"""
    refs = set()
    if not directory.exists(): return refs
    pattern = re.compile(rf'name="{attr_name}"\s+value="(\d+)"')
    for f in directory.rglob("*.xml"):
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        for m in pattern.finditer(text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
    return refs

def scan_string_mobs(directory):
    """String.wz: Mob.img中的imgdir name"""
    refs = set()
    if not directory.exists(): return refs
    for f in directory.rglob("*.xml"):
        if 'mob' not in f.name.lower(): continue
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        for m in re.finditer(r'<imgdir name="(\d+)">', text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
    return refs

def scan_scripts(directory):
    """JS脚本: 7位数字"""
    refs = set()
    if not directory.exists(): return refs
    for f in directory.rglob("*.js"):
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
    return refs

def scan_java(directory):
    """Java代码: 7位数字"""
    refs = set()
    if not directory.exists(): return refs
    for f in directory.rglob("*.java"):
        try: text = f.read_text(encoding='utf-8', errors='ignore')
        except: continue
        for m in re.finditer(r'(?<!\d)(\d{7})(?!\d)', text):
            val = int(m.group(1))
            if val in all_mobs: refs.add(val)
    return refs

# ========== 执行扫描 ==========
print("\n扫描中...")

map_refs = scan_map_spawns(WZ / "Map.wz")
print(f"  Map.wz刷怪:     {len(map_refs):>5} (type=m + string/int id)")

mob_refs = scan_mob_revive_summon(WZ / "Mob.wz")
print(f"  Mob.wz互引:     {len(mob_refs):>5} (revive/summon + 全部值)")

reactor_refs = scan_mob_attr(WZ / "Reactor.wz", "mob")
print(f"  Reactor.wz:     {len(reactor_refs):>5} (mob属性)")

item_refs = scan_mob_attr(WZ / "Item.wz", "mob")
print(f"  Item.wz掉落:    {len(item_refs):>5} (mob属性)")

quest_refs = scan_mob_attr(WZ / "Quest.wz", "mob")
print(f"  Quest.wz任务:   {len(quest_refs):>5} (mob属性)")

skill_refs = scan_mob_attr(WZ / "Skill.wz", "mob")
print(f"  Skill.wz技能:   {len(skill_refs):>5} (mob属性)")

string_refs = scan_string_mobs(WZ / "String.wz")
print(f"  String.wz名字:  {len(string_refs):>5} (Mob.img imgdir)")

zh_refs = scan_string_mobs(WZ_ZH / "String.wz")
zh_refs |= scan_mob_attr(WZ_ZH / "Quest.wz", "mob")
zh_refs |= scan_mob_attr(WZ_ZH / "Etc.wz", "mob")
print(f"  wz-zh-CN:       {len(zh_refs):>5} (String+Quest+Etc)")

script_refs = scan_scripts(ROOT / "gms-server" / "scripts-zh-CN")
print(f"  脚本:           {len(script_refs):>5} (7位数字)")

java_refs = scan_java(ROOT / "gms-server" / "src")
print(f"  Java代码:       {len(java_refs):>5} (7位数字)")

cat_path = ROOT / "gms-server" / "src" / "main" / "resources" / "mob-catalog" / "catalog.json"
cat_refs = set()
if cat_path.exists():
    with open(cat_path) as f:
        for mob in json.load(f).get("mobs", []):
            mid = mob.get("id")
            if mid and mid in all_mobs: cat_refs.add(mid)
print(f"  mob-catalog:    {len(cat_refs):>5}")

# ========== 合并 ==========
all_refs = map_refs | mob_refs | reactor_refs | item_refs | quest_refs | skill_refs | string_refs | zh_refs | script_refs | java_refs | cat_refs
referenced = all_refs & all_mobs
unreferenced = all_mobs - referenced

print(f"\n{'='*60}")
print(f"总计引用: {len(referenced)} / {len(all_mobs)}")
print(f"未引用:   {len(unreferenced)}")

# ========== 未引用详情 ==========
unref_sizes = []
for mid in unreferenced:
    fpath = MOB_DIR / f"{mid}.img"
    if fpath.exists():
        unref_sizes.append((mid, fpath.stat().st_size))
unref_sizes.sort(key=lambda x: -x[1])

total_unref = sum(s for _, s in unref_sizes)
total_all = sum(f.stat().st_size for f in MOB_DIR.glob("*.img"))
print(f"未引用大小: {total_unref/1024/1024:.1f}MB / {total_all/1024/1024:.1f}MB ({total_unref/total_all*100:.1f}%)")

# 分类
cats = defaultdict(list)
for mid, size in unref_sizes:
    cats[str(mid)[:2]].append((mid, size))

print(f"\n按前缀分类:")
print(f"{'前缀':<8}{'数量':<6}{'大小':>10}{'示例'}")
print(f"{'─'*60}")
for p in sorted(cats.keys()):
    items = cats[p]
    total = sum(s for _, s in items)
    ex = ', '.join(str(m) for m, _ in sorted(items)[:3])
    if len(items) > 3: ex += f' (+{len(items)-3})'
    sz = f"{total/1024/1024:.1f}M" if total >= 1024*1024 else f"{total/1024:.0f}K"
    print(f"{p}xxxxx  {len(items):<6}{sz:>10}  {ex}")

print(f"\nTop100:")
print(f"{'#':<5}{'ID':<12}{'大小':>10}")
print(f"{'─'*27}")
for i, (mid, size) in enumerate(unref_sizes[:100], 1):
    sz = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
    print(f"{i:<5}{mid:<12}{sz:>10}")

out = ROOT / "docs" / "unreferenced-mobs.txt"
with open(out, 'w') as f:
    f.write(f"未引用怪物 (V3精确扫描)\n总计: {len(unref_sizes)}个, {total_unref/1024/1024:.1f}MB\n{'='*60}\n\n")
    for i, (mid, size) in enumerate(unref_sizes, 1):
        sz = f"{size/1024/1024:.1f}M" if size >= 1024*1024 else f"{size/1024:.0f}K"
        f.write(f"{i:>4}. {mid}  ({sz})\n")
print(f"\n保存: {out}")
