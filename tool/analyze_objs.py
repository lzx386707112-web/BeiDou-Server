import xml.etree.ElementTree as ET, os, re

MAPDIR = "/Users/lizixian/Documents/mxd/BeiDou-Server/gms-server/wz/Map.wz/Map/Map4"

def parse_objs(path):
    txt = open(path, encoding="utf-8").read()
    # crude: capture each <imgdir name="X"> under obj that has UOL strings l0..l7
    objs = []
    # find obj sections
    # We'll parse with ET but extract string l* which are UOLs (may start with '../' or 'Map/')
    root = ET.parse(path).getroot()
    for section in root:
        if section.get("name") == "obj" or (section.get("name").isdigit() and False):
            pass
    # Actually obj is a top-level section
    for top in root:
        if top.get("name") == "obj":
            for o in top:
                d = {c.get("name"): c.get("value") for c in o}
                uols = {k: v for k, v in d.items() if re.match(r'l\d+', k) and v and ('Map/' in v or v.startswith('../') or '/' in v)}
                objs.append((d.get("oS"), uols))
    return objs

def parse_life(path):
    root = ET.parse(path).getroot()
    life = []
    for top in root:
        if top.get("name") == "life":
            for l in top:
                d = {c.get("name"): c.get("value") for c in l}
                life.append((d.get("type"), d.get("id")))
    return life

for f in ["450005220","450005242"]:
    print(f"\n===== {f} OBJ UOLs =====")
    objs = parse_objs(os.path.join(MAPDIR, f+".img.xml"))
    seen = set()
    for oS, uols in objs:
        key = (oS, tuple(sorted(uols.items())))
        if key in seen: continue
        seen.add(key)
        print(f"  oS={oS} uols={uols}")
    print(f"  life:", parse_life(os.path.join(MAPDIR, f+".img.xml")))
