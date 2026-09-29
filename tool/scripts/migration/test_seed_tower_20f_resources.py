#!/usr/bin/env python3
"""Independent installed-resource, dependency, raw-scope and delivery checks."""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

spec = importlib.util.spec_from_file_location("seed_migration", Path(__file__).with_name("migrate_seed_tower_20f.py"))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)
a = m.a
ROOT = m.ROOT
DELIVERY = Path("/Users/lizixian/Downloads/起源之塔前20层")
SCRIPTS = ["gms-server/scripts/event/SeedTower20.js", "gms-server/scripts/npc/2540000.js",
           "gms-server/scripts/portal/seedTower.js", "gms-server/scripts-zh-CN/npc/9900001.js",
           "gms-server/scripts-zh-CN/event/SeedTower20.js",
           *[f"gms-server/scripts/reactor/{rid}.js" for rid in sorted(m.REACTORS)]]


def xml_semantic(n):
    tag = n.tag
    if tag == "imgdir":
        return {c.get("name"): xml_semantic(c) for c in n}
    if tag == "canvas":
        return ("canvas", int(n.get("width")), int(n.get("height")), {c.get("name"): xml_semantic(c) for c in n})
    if tag == "vector":
        return (int(n.get("x")), int(n.get("y")))
    if tag == "null":
        return None
    if tag == "sound":
        return ("sound", int(n.get("length_ms")), int(n.get("bytes")))
    if tag == "extended":
        return [xml_semantic(c) for c in n]
    value = n.get("value")
    return int(value) if tag in {"int", "short", "long"} else float(value) if tag in {"float", "double"} else value


def img_semantic(n):
    if isinstance(n, a.WzCanvasProperty):
        return ("canvas", n.width, n.height, {c.name: img_semantic(c) for c in n.children()})
    if isinstance(n, a.WzSubProperty):
        return {c.name: img_semantic(c) for c in n.children()}
    if isinstance(n, a.WzConvexProperty):
        return [img_semantic(c) for c in n.children()]
    if isinstance(n, a.WzSoundProperty):
        return ("sound", n.length_ms, n._data_length)
    return n.value


def load(relative):
    im = a.load_image(ROOT / relative, a.GMS_KEY)
    assert not im.truncated and not im.parse_warnings, relative
    return im


def decoder_parity(parsed):
    samples = [parsed["clien/Data/Item/Etc/0400.img"].root.get("04009900/info/icon")]
    for mid in [9309400, 9309401, 9309402, 9309116, 9309123]:
        image = parsed[f"clien/Data/Mob/{mid}.img"]
        samples.append(next(n for n, _ in a.walk(image.root) if isinstance(n, a.WzCanvasProperty)))
    for canvas in samples:
        fast = m.decode_4444(canvas)
        reference = a.decode_canvas(canvas, region="GMS")
        assert fast.size == reference.size and fast.tobytes() == reference.tobytes()
    return len(samples)


CONNECT_ASSET = "clien/Data/Map/Obj/connect.img"


def connect_style_table(parsed):
    """`(kind, style) -> piece count` for the client's rope/ladder asset.

    The compatibility gate for a `connect` object is that
    `connect/{l0}/{l1}/{l2}` resolves in `connect.img`, not that `l1` sits in
    some fixed small set: untouched GMS towns already use rope styles up to 43.
    """
    asset = parsed.get(CONNECT_ASSET) or load(CONNECT_ASSET)
    return {(kind.name, style.name): len(style.children())
            for kind in asset.root.children() if isinstance(kind, a.WzSubProperty)
            for style in kind.children()}


def validate():
    manifest = json.loads(m.MANIFEST.read_text())
    parsed = {}
    audit = m.Migration()
    raw_protected = 0
    for relative, digest in manifest["files"].items():
        data = (ROOT / relative).read_bytes()
        assert m.sha(data) == digest, relative
        if relative.endswith(".img"):
            roots = {tuple(p) for p in manifest["raw_insert_roots"].get(relative, [])}
            parsed[relative] = audit.validate_img(relative, data, roots or None)
        if relative.endswith(".xml"):
            ET.fromstring(data)
    for relative, paths in manifest["raw_insert_roots"].items():
        before = (m.BASE / relative).read_bytes()
        assert m.sha(before) == manifest["baseline"][relative], relative
        after = (ROOT / relative).read_bytes()
        roots = {tuple(p) for p in paths}
        a.verify_raw_record_insert_scope(before, after, roots)
        records, _ = a.raw_record_state(before)
        raw_protected += sum(not any(p[:len(r)] == r or r[:len(p)] == p for r in roots) for p in records)
        if relative.startswith("clien/Data/String/"):
            xml_paths = [relative.replace("clien/Data/String/", f"gms-server/{tree}/String.wz/")+".xml"
                         for tree in ["wz", "wz-zh-CN"]]
        elif relative.startswith("clien/Data/Item/"):
            xml_paths = [relative.replace("clien/Data/Item/", "gms-server/wz/Item.wz/")+".xml"]
        else:
            xml_paths = []
        for xml_path in xml_paths:
            old = ET.parse(m.BASE / xml_path).getroot()
            new = ET.parse(ROOT / xml_path).getroot()
            for path in roots:
                parent = new
                for name in path[:-1]:
                    parent = next(c for c in parent if c.get("name") == name)
                added = next(c for c in parent if c.get("name") == path[-1])
                assert img_semantic(parsed[relative].root.get("/".join(path))) == xml_semantic(added), (xml_path, path)
                parent.remove(added)
            assert ET.tostring(old) == ET.tostring(new), xml_path
    parity = decoder_parity(parsed)
    connect_styles = connect_style_table(parsed)
    legacy = {"clien/Data/String/Skill.img"}
    dependencies = 0
    for mid in m.MAP_IDS:
        relative = f"clien/Data/Map/Map/Map9/{mid}.img"
        im = parsed[relative]
        xml = ROOT / f"gms-server/wz/Map.wz/Map/Map9/{mid}.img.xml"
        assert img_semantic(im.root) == xml_semantic(ET.parse(xml).getroot()), mid
        f = (mid - 992000000) // 1000
        info = im.root.child("info")
        assert a.child_value(info, "forcedReturn") == (992000000 if f else 100000000)
        for n, p in a.walk(im.root):
            assert n.name not in {"spineAni", "questex", "tags", "timeScale"}, (mid, p)
        containers = [im.root.child("back")] + [c.child("obj") for c in im.root.children() if c.name.isdigit()]
        for c in containers:
            if c:
                assert [int(n.name) for n in c.children()] == list(range(len(c.children()))), (mid, c.name)
        for layer in [c for c in im.root.children() if c.name.isdigit()]:
            for n in layer.child("obj").children() if layer.child("obj") else []:
                if a.child_value(n, "oS") == "connect":
                    kind = str(a.child_value(n, "l0"))
                    style = str(a.child_value(n, "l1"))
                    piece = int(a.child_value(n, "l2"))
                    pieces = connect_styles.get((kind, style))
                    assert pieces is not None, (mid, kind, style)
                    assert 0 <= piece < pieces, (mid, kind, style, piece, pieces)
        deps = a.collect_dependencies(im)
        for (kind, name), branches in deps["assets"].items():
            path = f"clien/Data/Map/{kind}/{name}.img"
            asset = parsed.get(path) or load(path)
            for branch in branches:
                assert asset.root.get(branch) is not None, (mid, path, branch)
                dependencies += 1
            if not name.startswith("seed"):
                legacy.add(path)
        for id in deps["mobs"]:
            assert id in m.MOBS
        for id in deps["npcs"]:
            assert id == 2540000
        for portal in im.root.child("portal").children():
            assert int(a.child_value(portal,"pt")) in {0,1,2,3,7,9}, (mid, portal.name)
            script = a.child_value(portal,"script")
            if script:
                assert script == "seedTower", (mid, script)
        if f == 14:
            assert any(a.child_value(p,"pn")=="out00" for p in im.root.child("portal").children())
    for mid in sorted(m.MOBS | set(m.HAZARDS)):
        im = parsed[f"clien/Data/Mob/{mid}.img"]
        xml = ET.parse(ROOT / f"gms-server/wz/Mob.wz/{mid}.img.xml").getroot()
        assert img_semantic(im.root) == xml_semantic(xml), mid
        info = im.root.child("info")
        assert not isinstance(info.child("mobType"), a.WzStringProperty), mid
        for attack in [n for n in im.root.children() if n.name.startswith("attack")]:
            ai = attack.child("info")
            if ai and ai.child("ball"):
                assert a.child_value(ai,"type") == 2 and a.child_value(ai,"bulletSpeed") > 0, mid
                if ai.child("hit"):
                    assert a.child_value(ai.child("hit"),"attach") == 1, mid
        link = a.child_value(info,"link")
        if link and int(link) not in m.MOBS:
            legacy.add(f"clien/Data/Mob/{int(link):07d}.img")
    for kind, ids in [("Reactor", m.REACTORS), ("Npc", {2540000})]:
        for id in ids:
            image = parsed[f"clien/Data/{kind}/{id}.img"]
            xml = ET.parse(ROOT / f"gms-server/wz/{kind}.wz/{id}.img.xml").getroot()
            assert img_semantic(image.root) == xml_semantic(xml), (kind, id)
    item = parsed["clien/Data/Item/Etc/0400.img"]
    strings = parsed["clien/Data/String/Etc.img"]
    xml_items = ET.parse(ROOT / "gms-server/wz/Item.wz/Etc/0400.img.xml").getroot()
    for iid in m.ITEMS:
        node = item.root.child("0"+str(iid)); assert node is not None
        assert strings.root.get(f"Etc/{iid}/name") is not None
        assert a.child_value(node.child("info"),"tradeBlock") == 1
        server = next(c for c in xml_items if c.get("name")==node.name)
        assert img_semantic(node) == xml_semantic(server), iid
    for path in sorted(legacy):
        baseline = subprocess.check_output(["rtk", "proxy", "git", "cat-file", "blob", "HEAD:"+path], cwd=ROOT)
        assert (ROOT / path).read_bytes() == baseline, path
    script_text = (ROOT / SCRIPTS[0]).read_text()
    assert script_text == (ROOT / "gms-server/scripts-zh-CN/event/SeedTower20.js").read_text(), "localized event registration"
    data_text = script_text.split("var SEED_DATA = ",1)[1].split(";\n// END SEED DATA",1)[0]
    data = json.loads(data_text)
    assert len(data)==21 and len(data["19"]["route"])>30
    assert data["19"]["route"][0][:2]==[-1195,104] and data["19"]["route"][-1][:2]==[2130,-1117]
    for script in SCRIPTS:
        subprocess.run(["rtk","proxy","node","--check",str(ROOT/script)],check=True)
    subprocess.run(["rtk","proxy","node",str(Path(__file__).with_name("test_seed_tower_20f_contract.js"))],check=True)
    print(f"Resources: {len(manifest['files'])} hashes; {audit.canvas_count} Canvas decodes; "
          f"{raw_protected} protected raw records; {dependencies} map asset paths; "
          f"{len(legacy)} legacy files unchanged; {parity} reference decoder matches")
    return manifest


def idempotence(manifest):
    expected = dict(manifest["files"])
    for relative in SCRIPTS + [str(m.MANIFEST.relative_to(ROOT))]:
        expected[relative] = m.sha((ROOT / relative).read_bytes())
    subprocess.run(["rtk", "proxy", sys.executable, str(Path(__file__).with_name("migrate_seed_tower_20f.py")),
                    "--install"], check=True)
    for relative, digest in expected.items():
        assert m.sha((ROOT / relative).read_bytes()) == digest, ("not idempotent", relative)
    print(f"Idempotence: {len(expected)} files unchanged after regeneration")


def deliver(manifest):
    files = dict(manifest["files"])
    files.update({r:m.sha((ROOT/r).read_bytes()) for r in SCRIPTS})
    assert DELIVERY.parent == Path("/Users/lizixian/Downloads")
    if DELIVERY.exists():
        raise RuntimeError("Delivery exists; inspect and archive the exact previous task folder before recreating")
    for relative, digest in sorted(files.items()):
        target = DELIVERY / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/relative, target)
        assert m.sha(target.read_bytes()) == digest, relative
    report = {"directory":str(DELIVERY),"files":files,"server_jar_built":False,
              "java_sources_in_repository":["gms-server/src/main/java/org/gms/server/life/SeedTowerCompat.java",
                 *[f"gms-server/src/main/java/org/gms/net/server/channel/handlers/{name}.java" for name in
                   ["CloseRangeDamageHandler","RangedAttackHandler","MagicDamageHandler","MoveLifeHandler"]],
                 "gms-server/src/main/java/org/gms/server/maps/MapleMap.java",
                 "gms-server/src/main/java/org/gms/server/maps/Reactor.java"]}
    a.atomic_write_text(ROOT/"docs/migrations/seed-tower-20f-delivery.json",json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(f"Delivered {len(files)} runtime files with matching hashes to {DELIVERY}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deliver",action="store_true")
    parser.add_argument("--idempotence",action="store_true")
    args = parser.parse_args()
    manifest = validate()
    if args.idempotence:
        idempotence(manifest)
    if args.deliver:
        deliver(manifest)
