import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey, WzCanvasProperty

BASE = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map"
MAP4 = f"{BASE}/Map/Map4"
_cache = {}
def load_img(rel):
    if rel in _cache: return _cache[rel]
    d = open(f"{BASE}/{rel}","rb").read()
    r = detect_region_from_img(d)
    img = WzImage.from_bytes(d, key=WzKey.for_region(r), name=rel)
    _cache[rel] = img.parse()
    return _cache[rel]

def back_entries(rel):
    root = load_img(f"Map/Map4/{rel}")
    out = []
    back = root.child("back")
    if back:
        for b in back.children():
            bS = no = None
            for ch in b.children():
                if ch.name=="bS": bS=ch.value
                elif ch.name=="no": no=ch.value
            out.append((int(b.name), bS, no))
    return out

def frame_canvas(bS, no):
    try:
        root = load_img(f"Back/{bS}.img")
    except Exception as e:
        return f"NO FILE {bS}.img ({e})"
    node = root.child(str(no))
    if node is None:
        return f"NO FRAME {no} in {bS}.img"
    # find canvas
    canvas = None
    if isinstance(node, WzCanvasProperty):
        canvas = node
    else:
        for ch in node.children():
            if isinstance(ch, WzCanvasProperty):
                canvas = ch; break
    if canvas is None:
        return f"NO CANVAS in {bS}/{no}"
    w = getattr(canvas, "width", None)
    h = getattr(canvas, "height", None)
    fmt = getattr(canvas, "format", None)
    fmt2 = getattr(canvas, "format2", None)
    # also report child keys
    keys = [c.name for c in canvas.children()]
    return f"canvas {w}x{h} format={fmt} format2={fmt2} keys={keys}"

for f in ["450005220.img","450005242.img","450005240.img","450005241.img"]:
    print(f"\n=== {f} back frames ===")
    for (idx,bS,no) in sorted(back_entries(f)):
        c = frame_canvas(bS, no) if bS else "no bS"
        flag = ""
        if "canvas" in c and "970" in c: flag = "  <-- LARGE/MODERN?"
        print(f"  back/{idx}: {bS} no={no} -> {c}{flag}")
