import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey

BASE = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map"
MAP4 = f"{BASE}/Map/Map4"

_cache = {}
def load_img(relpath):
    if relpath in _cache: return _cache[relpath]
    p = f"{BASE}/{relpath}"
    data = open(p, "rb").read()
    region = detect_region_from_img(data)
    img = WzImage.from_bytes(data, key=WzKey.for_region(region), name=relpath)
    root = img.parse()
    _cache[relpath] = root
    return root

def walk_exist(node, parts):
    cur = node
    for p in parts:
        if cur is None or not cur.has_children(): return False
        nxt = cur.child(p)
        if nxt is None: return False
        cur = nxt
    return True

def map_refs(relpath):
    root = load_img(relpath)
    objs = set()
    backs = set()
    for sec in root.children():
        if sec.name == "back" and sec.has_children():
            for b in sec.children():
                bS = bS_no = None
                for ch in b.children():
                    if ch.name == "bS": bS = ch.value
                    if ch.name == "no": bS_no = ch.value
                if bS is not None:
                    backs.add((bS, bS_no))
        if sec.name.isdigit():
            for sub in sec.children():
                if sub.name == "obj" and sub.has_children():
                    for o in sub.children():
                        oS=l0=l1=l2=None
                        for ch in o.children():
                            if ch.name=="oS": oS=ch.value
                            elif ch.name=="l0": l0=ch.value
                            elif ch.name=="l1": l1=ch.value
                            elif ch.name=="l2": l2=ch.value
                        if oS: objs.add((oS,l0,l1,l2))
    return objs, backs

# Determine existence of referenced sprites
def check_obj(oS,l0,l1,l2):
    try:
        root = load_img(f"Obj/{oS}.img")
    except Exception:
        return f"MISSING FILE Obj/{oS}.img"
    parts = [p for p in (l0,l1,l2) if p is not None]
    if not walk_exist(root, parts):
        return f"BROKEN PATH Obj/{oS}.img/{'/'.join(parts)}"
    return None

def check_back(bS, no):
    try:
        root = load_img(f"Back/{bS}.img")
    except Exception:
        return f"MISSING FILE Back/{bS}.img"
    # back frame no: typically <no> child under root, or frame index
    # arcana2 backdrop: frames are 0..n under root
    if root.child(str(no)) is None and root.child(str(int(no))) is None:
        # try as frame group
        if not walk_exist(root, [str(no)]):
            return f"BROKEN FRAME Back/{bS}.img frame {no}"
    return None

for f in ["450005220.img","450005242.img","450005240.img","450005241.img"]:
    objs, backs = map_refs(f"Map/Map4/{f}")
    print(f"\n=== {f} ===  objs={len(objs)} backs={len(backs)}")
    for (oS,l0,l1,l2) in sorted(objs):
        err = check_obj(oS,l0,l1,l2)
        if err: print(f"   OBJ {err}")
    for (bS,no) in sorted(backs):
        err = check_back(bS,no)
        if err: print(f"   BACK {err}")
