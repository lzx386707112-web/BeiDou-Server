import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey, WzCanvasProperty

BASE = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map"
MAP4 = f"{BASE}/Map/Map4"
_cache = {}
def load(rel):
    if rel in _cache: return _cache[rel]
    d = open(f"{BASE}/{rel}","rb").read()
    r = detect_region_from_img(d)
    img = WzImage.from_bytes(d, key=WzKey.for_region(r), name=rel)
    _cache[rel] = img.parse()
    return _cache[rel]

def obj_paths(rel):
    root = load(f"Map/Map4/{rel}")
    out = set()
    for sec in root.children():
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
                        if oS: out.add((oS,l0,l1,l2))
    return out

def canvas_of(oS,l0,l1,l2):
    try:
        root = load(f"Obj/{oS}.img")
    except Exception as e:
        return f"NOFILE {oS}.img"
    node = root
    for p in (l0,l1,l2):
        if p is None: break
        if node is None or not node.has_children(): return f"BROKEN at {p}"
        node = node.child(p)
        if node is None: return f"BROKEN at {p}"
    if node is None: return "NULL"
    # node may be a canvas or subproperty containing canvas
    if isinstance(node, WzCanvasProperty):
        return f"canvas {node.width}x{node.height} fmt={node.format}"
    # find first canvas child
    for ch in node.children():
        if isinstance(ch, WzCanvasProperty):
            return f"canvas {ch.width}x{ch.height} fmt={ch.format}"
    return f"node type={type(node).__name__} (no canvas) children={[c.name for c in node.children()][:8]}"

maps = ["450005220.img","450005242.img","450005240.img","450005241.img"]
paths = {m: obj_paths(m) for m in maps}
crash = paths["450005220.img"] | paths["450005242.img"]
work = paths["450005240.img"] | paths["450005241.img"]
print("obj path counts: 220=%d 242=%d 240=%d 241=%d" % (len(paths["450005220.img"]),len(paths["450005242.img"]),len(paths["450005240.img"]),len(paths["450005241.img"])))
print("\nOBJ paths UNIQUE to crash maps (not in any working map):")
for p in sorted(crash - work):
    print("  ", p, "->", canvas_of(*p))
print("\nOBJ paths UNIQUE to working maps:")
for p in sorted(work - crash):
    print("  ", p)
