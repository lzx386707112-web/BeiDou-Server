#!/usr/bin/env python3
import re
from pathlib import Path

# Find unique map files with864xxxx mob spawns
maps = set()
for f in Path('gms-server/wz/Map.wz/Map/Map4').glob('*.xml'):
    try:
        t = f.read_text(encoding='utf-8', errors='ignore')
        if re.search(r'value="864\d{4}"', t):
            maps.add(f.stem)
    except:
        pass

print(f'Map4 files with864xxxx mobs: {len(maps)}')

# Look up names in String.wz
str_path = Path('gms-server/wz-zh-CN/String.wz/Map.img.xml')
names = {}
if str_path.exists():
    text = str_path.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'<imgdir name="(\d+)">\s*<string name="streetName" value="([^"]*?)"/>\s*<string name="mapName" value="([^"]*?)"/>', text):
        mid, street, name = m.group(1), m.group(2), m.group(3)
        if mid in maps:
            names[mid] = f'{street} - {name}'

# Group by street
from collections import defaultdict
streets = defaultdict(list)
for mid, fullname in names.items():
    street = fullname.split(' - ')[0] if ' - ' in fullname else fullname
    streets[street].append(mid)

print(f'\nBy street:')
for street in sorted(streets.keys()):
    mids = sorted(streets[street])
    print(f'  {street}: {len(mids)} maps')

print(f'\nAll map names ({len(names)}):')
for mid in sorted(names.keys()):
    print(f'  {mid}: {names[mid]}')
