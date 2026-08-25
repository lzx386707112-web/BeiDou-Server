import xml.etree.ElementTree as ET, os

MAPDIR = "/Users/lizixian/Documents/mxd/BeiDou-Server/gms-server/wz/Map.wz/Map/Map4"

def obj_paths(path):
    root = ET.parse(path).getroot()
    paths = set()
    for top in root:
        sn = top.get("name")
        if sn.isdigit():  # layer
            for sub in top:
                if sub.get("name") == "obj":
                    for o in sub:
                        d = {c.get("name"): c.get("value") for c in o}
                        oS = d.get("oS"); l0=d.get("l0"); l1=d.get("l1"); l2=d.get("l2")
                        if oS:
                            paths.add((oS, l0, l1, l2))
    return paths

def life_ids(path):
    root = ET.parse(path).getroot()
    s = set()
    for top in root:
        if top.get("name") == "life":
            for l in top:
                d = {c.get("name"): c.get("value") for c in l}
                s.add((d.get("type"), d.get("id")))
    return s

crash = ["450005220","450005242"]
work = ["450005210","450005221","450005230","450005240","450005241","450005200"]

cp = {f: obj_paths(os.path.join(MAPDIR,f+".img.xml")) for f in crash+work}
cl = {f: life_ids(os.path.join(MAPDIR,f+".img.xml")) for f in crash+work}

crashed_obj = set().union(*[cp[f] for f in crash])
work_obj = set().union(*[cp[f] for f in work])
print("OBJ paths unique to CRASH maps (not in any working map):")
for p in sorted(crashed_obj - work_obj):
    print("   ", p)
print()
print("total crash obj paths:", len(crashed_obj), " work obj paths:", len(work_obj))
print()
print("LIFE ids in crash maps:")
for f in crash:
    print(f, sorted(cl[f]))
print()
print("LIFE ids in working maps:")
for f in work:
    print(f, sorted(cl[f]))
