import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey, WzUolProperty

CLIENT = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map/Map/Map4"

def load(path):
    data = open(path, "rb").read()
    region = detect_region_from_img(data)
    return WzImage.from_bytes(data, key=WzKey.for_region(region), name=path).parse(), region

root, _ = load(f"{CLIENT}/450005242.img")
count = 0
for sec in root.children():
    if sec.name.isdigit():
        for sub in sec.children():
            if sub.name == "obj" and sub.has_children():
                for e in sub.children():
                    print(f"layer {sec.name} obj '{e.name}':")
                    for ch in e.children():
                        v = getattr(ch, "value", None)
                        print(f"   {ch.name} ({type(ch).__name__}) = {repr(v)}")
                    count += 1
                    if count >= 2:
                        break
            if count >= 2: break
        if count >= 2: break
    if count >= 2: break
