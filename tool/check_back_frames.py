import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey, WzCanvasProperty

BASE = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map"
def load(rel):
    d = open(f"{BASE}/{rel}","rb").read()
    r = detect_region_from_img(d)
    return WzImage.from_bytes(d, key=WzKey.for_region(r), name=rel).parse()

def back_entries(rel):
    root = load(f"Map/Map4/{rel}")
    out = []
    back = root.child("back")
    for b in back.children():
        bS=no=None
        for ch in b.children():
            if ch.name=="bS": bS=ch.value
            elif ch.name=="no": no=ch.value
        out.append((int(b.name), bS, no))
    return out

def frame_info(bS, no):
    root = load(f"Back/{bS}.img")
    node = root.child("back") if root.child("back") else root
    f = node.child(str(no))
    if f is None: return f"MISSING frame {no}"
    if isinstance(f, WzCanvasProperty):
        return f"canvas {f.width}x{f.height} fmt={f.format} fmt2={getattr(f,'format2',None)}"
    for ch in f.children():
        if isinstance(ch, WzCanvasProperty):
            return f"canvas {ch.width}x{ch.height} fmt={ch.format} fmt2={getattr(ch,'format2',None)}"
    return "no canvas"

for m in ["450005220.img","450005242.img","450005240.img","450005241.img"]:
    print(f"\n=== {m} ===")
    for (idx,bS,no) in sorted(back_entries(m)):
        info = frame_info(bS,no)
        bad = ""
        if "canvas" in info:
            import re
            mt = re.search(r"(\d+)x(\d+) fmt=(\S+)", info)
            if mt:
                w,h,fmt = int(mt.group(1)),int(mt.group(2)),mt.group(3)
                if fmt not in ("1","1.0") or w>2000 or h>2000:
                    bad = "  <<< SUSPECT (non-ARGB4444 or oversized)"
        print(f"  back/{idx}: {bS} no={no} -> {info}{bad}")
