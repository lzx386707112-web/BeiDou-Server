import io, sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey

CLIENT = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map/Map/Map4"

def load(path):
    data = open(path, "rb").read()
    region = detect_region_from_img(data)
    img = WzImage.from_bytes(data, key=WzKey.for_region(region), name=path)
    return img.parse(), region

def walk(node, path=""):
    out = []
    for c in node.children():
        out.append((path + "/" + c.name, type(c).__name__))
        if hasattr(c, "children") and c.has_children():
            out.extend(walk(c, path + "/" + c.name))
    return out

for f in ["450005220.img","450005242.img","450005240.img","450005241.img"]:
    try:
        root, region = load(f"{CLIENT}/{f}")
        # top-level section names
        secs = [(c.name, type(c).__name__, c.child_count() if hasattr(c,'child_count') else '?') for c in root.children()]
        print(f"\n=== {f} region={region} ===")
        print("  top-level sections:", secs)
        # show one obj entry structure under a numbered layer
        for sec in root.children():
            if sec.name.isdigit():
                for sub in sec.children():
                    if sub.name == "obj" and sub.has_children():
                        sample = sub.children()[0]
                        print(f"  sample obj entry '{sample.name}':")
                        for ch in sample.children():
                            val = getattr(ch, 'value', None)
                            print(f"     {ch.name} ({type(ch).__name__}) = {val}")
                        break
                break
    except Exception as e:
        print(f"\n=== {f} PARSE ERROR: {type(e).__name__}: {e}")
