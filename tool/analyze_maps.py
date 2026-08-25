import xml.etree.ElementTree as ET
import os, glob

MAPDIR = "/Users/lizixian/Documents/mxd/BeiDou-Server/gms-server/wz/Map.wz/Map/Map4"

def get(node, name, default=None):
    for c in node:
        if c.tag == "imgdir" and c.get("name") == name:
            return c
    return None

def parse_map(path):
    tree = ET.parse(path)
    root = tree.getroot()
    m = {"back": [], "tiles": [], "objs": [], "life": [], "portals": []}
    for section in root:
        sn = section.get("name")
        if sn == "back":
            for b in section:
                d = {c.get("name"): c.get("value") for c in b}
                m["back"].append((d.get("bS"), int(d.get("no", -1))))
        elif sn == "life":
            for l in section:
                d = {c.get("name"): c.get("value") for c in l}
                m["life"].append((d.get("type"), d.get("id")))
        elif sn == "portal":
            for p in section:
                d = {c.get("name"): c.get("value") for c in p}
                m["portals"].append(d.get("tn", ""))
        elif sn.isdigit():
            # a layer
            for sub in section:
                if sub.get("name") == "tile":
                    for t in sub:
                        d = {c.get("name"): c.get("value") for c in t}
                        m["tiles"].append((d.get("u"), int(d.get("no", -1))))
                elif sub.get("name") == "obj":
                    for o in sub:
                        d = {c.get("name"): c.get("value") for c in o}
                        m["objs"].append((d.get("oS"), d.get("u"), int(d.get("no", -1))))
    return m

crash = ["450005220", "450005242"]
# pick several working siblings
work = ["450005210", "450005221", "450005230", "450005240", "450005241"]

cmaps = {f: parse_map(os.path.join(MAPDIR, f+".img.xml")) for f in crash+work}

for f in crash:
    print(f"\n===== CRASH {f} =====")
    print("  back bS/no:", sorted(set(cmaps[f]["back"])))
    print("  life:", sorted(set(cmaps[f]["life"])))
    print("  portals:", sorted(set(cmaps[f]["portals"])))
    print("  #tiles:", len(cmaps[f]["tiles"]), " tile u/no:", sorted(set(cmaps[f]["tiles"])))
    print("  #objs:", len(cmaps[f]["objs"]), " obj oS/u/no:", sorted(set(cmaps[f]["objs"])))
