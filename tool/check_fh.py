import xml.etree.ElementTree as ET, os

MAPDIR = "/Users/lizixian/Documents/mxd/BeiDou-Server/gms-server/wz/Map.wz/Map/Map4"

def collect(path):
    root = ET.parse(path).getroot()
    fh_ids = set()
    fh_links = []  # (id, prev, next)
    life_fh = []
    for top in root:
        sn = top.get("name")
        if sn == "foothold":
            for layer in top:          # foothold/layer
                for group in layer:    # /group
                    for fhf in group:  # /footholdId
                        fid = int(fhf.get("name"))
                        fh_ids.add(fid)
                        d = {c.get("name"): c.get("value") for c in fhf}
                        fh_links.append((fid, int(d.get("prev",-1)), int(d.get("next",-1))))
        if sn == "life":
            for l in top:
                d = {c.get("name"): c.get("value") for c in l}
                if d.get("type") == "m":
                    life_fh.append(int(d.get("fh", -1)))
    return fh_ids, fh_links, life_fh

for f in ["450005220","450005242","450005240","450005241"]:
    fh_ids, fh_links, life_fh = collect(os.path.join(MAPDIR, f+".img.xml"))
    missing_fh = sorted(set(life_fh) - fh_ids)
    # also check next/prev chains: in GMS a foothold's next/prev should point to existing id (or 0 sentinel)
    bad_links = []
    for fid, prev, nxt in fh_links:
        if prev not in fh_ids and prev != 0:
            bad_links.append((fid,'prev',prev))
        if nxt not in fh_ids and nxt != 0:
            bad_links.append((fid,'next',nxt))
    print(f"\n{f}: footholds={len(fh_ids)} mobs={len(life_fh)}")
    print(f"   mob fh NOT in foothold table: {missing_fh}")
    print(f"   foothold next/prev pointing to missing id: {bad_links[:20]}{'...' if len(bad_links)>20 else ''} (total {len(bad_links)})")
