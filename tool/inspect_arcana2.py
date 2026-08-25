import sys
sys.path.insert(0, "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/wz-python")
from wzpy import WzImage, detect_region_from_img, WzKey, WzCanvasProperty

BASE = "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/Data/Map"
d = open(f"{BASE}/Back/arcana2.img","rb").read()
r = detect_region_from_img(d)
img = WzImage.from_bytes(d, key=WzKey.for_region(r), name="arcana2.img")
root = img.parse()
print("top-level child count:", root.child_count())
names = [c.name for c in root.children()]
print("first 30 names:", names[:30])
print("any name '74'?", '74' in names, " '17'?", '17' in names)
# pick a frame and inspect its structure
for nm in names[:5]:
    node = root.child(nm)
    print(f"\nframe {nm}: type={type(node).__name__} child_count={node.child_count() if hasattr(node,'child_count') else '?'}")
    for ch in node.children()[:6]:
        v = getattr(ch,'value',None)
        sub = ch.child_count() if hasattr(ch,'child_count') else '?'
        print(f"   {ch.name} ({type(ch).__name__}) val={v} sub={sub}")
