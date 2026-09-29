#!/usr/bin/env python3
"""Seed 1-20: new legacy projections, raw inserts into shared item/string IMGs.

No existing map asset container is rewritten. Missing source branches are
materialized in Seed-only containers and only Seed maps are redirected there.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

from PIL import Image
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("seed_arc", HERE / "migrate_arcane_river_expansion.py")
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)

ROOT = a.ROOT
BASE = Path("/private/tmp/seed-tower-gameplay-baseline")
MANIFEST = ROOT / "docs/migrations/seed-tower-20f-manifest.json"
MAP_IDS = [992000000 + f * 1000 for f in range(21)]
MOBS = {9309000, 9309001, 9309002, 9309003, 9309004, 9309005,
        9309006, 9309007, 9309008, 9309012, 9309013, 9309033,
        9309042, 9309043, 9309044, 9309045, 9309046, 9309047,
        9309102, 9309103, 9309116, 9309117, 9309123, 9309125,
        9309126, 9309127, 9309131, 9309132, 9309201, 9309202,
        9309205, 9309209}
REACTORS = {9260004, 9260005, 9260006, 9260007, 9260020,
            9921000, 9921001, 9922002, 9922003}
HAZARDS = {9309400: "火柱", 9309401: "蓝色落石", 9309402: "绿色落石"}
ITEMS = [4000968, 4009237, 4009238, 4009497] + list(range(4009900, 4009929))
COLORS = ["蓝", "黄", "红", "绿"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode_4444(canvas):
    raw = a._decompress(canvas, a.GMS_KEY)
    if len(raw) != canvas.width * canvas.height * 2:
        raise RuntimeError("ARGB4444 payload length mismatch")
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(canvas.height, canvas.width, 2)
    lo, hi = pixels[:, :, 0], pixels[:, :, 1]
    rgba = np.stack(((hi & 15)*17, (lo >> 4)*17, (lo & 15)*17, (hi >> 4)*17), axis=2)
    return Image.fromarray(rgba)


def fresh(name):
    im = a.WzImage.from_bytes(b"", key=a.GMS_KEY, name=name)
    im._root = a.WzSubProperty(name)
    im._parsed = True
    return im


def clone(node, image, path, materializer, name=None):
    # Resolve local UOLs before isolating a branch in a different container.
    if isinstance(node, a.WzCanvasProperty):
        return a.clone_property(node, None, image, path, materializer, name)
    if isinstance(node, a.WzUolProperty):
        resolved = node.parent.get(str(node.value))
        if resolved is None or resolved is node:
            raise RuntimeError(f"unresolved UOL {path}:{node.name}={node.value}")
        return clone(resolved, image, path, materializer, name or node.name)
    if isinstance(node, a.WzSubProperty):
        out = a.WzSubProperty(name or node.name)
        for c in node.children():
            out.add(clone(c, image, path, materializer))
        return out
    return a.clone_property(node, None, image, path, materializer, name)


def projection(path, sanitizer=None):
    src = a.load_image(path, a.BMS_KEY)
    if sanitizer:
        sanitizer(src.root)
    mat = a.CanvasMaterializer()
    mat.max_edge = 0
    out = fresh(path.name)
    for c in src.root.children():
        out.root.add(clone(c, src, path, mat))
    return out


def scalar_node(name, values):
    n = a.WzSubProperty(name)
    for key, val in values.items():
        (a.set_string if isinstance(val, str) else a.set_int)(n, key, val)
    return n


def dense(n):
    if not n:
        return
    # These are new standalone maps, so renumbering is confined to new data.
    entries = list(n.children())
    n._children.clear()
    for i, c in enumerate(entries):
        c.name = str(i)
        n.add(c)


def sanitize_map(root, mid):
    floor = (mid - 992000000) // 1000
    for c in list(root.children()):
        if c.name not in a.MAP_ROOTS:
            a.remove_child(root, c.name)
    info = root.child("info")
    for field in a.MAP_INFO_UNSUPPORTED | {"timeLimit", "EscortMinTime", "moveLimit"}:
        a.remove_child(info, field)
    a.set_int(info, "returnMap", 992000000 if floor else 100000000)
    a.set_int(info, "forcedReturn", 992000000 if floor else 100000000)
    # Legacy darkness is supported; modern special field controllers are not.
    if floor == 17:
        a.set_int(info, "fieldType", 9)
        a.set_int(info, "hideMinimap", 1)
    life = root.child("life")
    for c in list(life.children()) if life else []:
        if a.child_value(c, "type") == "n":
            if floor or int(a.child_value(c, "id")) != 2540000:
                a.remove_child(life, c.name)
                continue
        for field in a.LIFE_UNSUPPORTED:
            a.remove_child(c, field)
    for layer in [c for c in root.children() if c.name.isdigit()]:
        objects = layer.child("obj")
        for c in list(objects.children()) if objects else []:
            if c.child("spineAni"):
                a.remove_child(objects, c.name)
                continue
            for field in a.OBJ_UNSUPPORTED:
                a.remove_child(c, field)
            if a.child_value(c, "oS") == "connect":
                if str(a.child_value(c, "l1")) not in {"0", "1", "2", "3", "4"}:
                    a.set_string(c, "l1", "0")
                a.set_string(c, "l2", str(max(0, min(4, int(a.child_value(c, "l2") or 0)))))
        dense(objects)
    back = root.child("back")
    for c in list(back.children()) if back else []:
        if int(a.child_value(c, "ani") or 0) == 2:
            a.remove_child(back, c.name)
        else:
            for field in a.BACK_UNSUPPORTED:
                a.remove_child(c, field)
    dense(back)
    portals = root.child("portal")
    for c in portals.children():
        pt = int(a.child_value(c, "pt") or 0)
        script = a.child_value(c, "script")
        if script or pt in {8, 11, 13, 16}:
            a.set_string(c, "script", "seedTower")
            a.set_int(c, "pt", 9 if pt in {9, 13, 16} else 7)
            a.set_int(c, "tm", 999999999)
        for field in a.PORTAL_UNSUPPORTED | {"verticalImpact", "sessionValueKey", "sessionValue", "reactorName"}:
            a.remove_child(c, field)
    if floor == 14:
        portals.add(scalar_node(str(len(portals.children())), {
            "pn": "out00", "pt": 7, "x": 373, "y": 327,
            "tm": 999999999, "tn": "", "script": "seedTower"}))
    if floor == 20:
        portals.add(scalar_node(str(len(portals.children())), {
            "pn": "roar", "pt": 7, "x": 580, "y": 131,
            "tm": 999999999, "tn": "", "script": "seedTower"}))
    if floor == 18:
        for c in root.child("reactor").children():
            a.set_string(c, "name", "seed" + c.name)
            a.set_int(c, "reactorTime", 15)
    if floor == 7:
        for layer in [c for c in root.children() if c.name.isdigit()]:
            objects = layer.child("obj")
            for c in objects.children() if objects else []:
                if a.child_value(c, "oS") == "trap" and a.child_value(c, "l1") == "animal":
                    x, y = a.child_value(c, "x"), a.child_value(c, "y")
                    # A real legacy projectile shooter supplements the source moving trap.
                    fh = min((n for n, _ in a.walk(root.child("foothold")) if n.child("x1")),
                             key=lambda n: abs(a.child_value(n, "x1") - x) + abs(a.child_value(n, "y1") - y))
                    life.add(scalar_node(str(len(life.children())), {"type": "m", "id": "9309125",
                        "x": x, "y": y - 20, "cy": y, "fh": int(fh.name),
                        "rx0": x - 50, "rx1": x + 50, "mobTime": 0, "f": 0, "hide": 0}))


def route_from(root):
    ni = root.child("nodeInfo")
    nodes = {}
    for n in ni.children():
        if n.name.isdigit():
            nodes[int(a.child_value(n, "key"))] = n
    start, end = int(a.child_value(ni, "start")), int(a.child_value(ni, "end"))
    todo = deque([[start]])
    seen = {start}
    while todo:
        path = todo.popleft()
        if path[-1] == end:
            return [[int(a.child_value(nodes[k], "x")), int(a.child_value(nodes[k], "y")),
                     int(a.child_value(nodes[k], "attr") or 0)] for k in path]
        for edge in nodes[path[-1]].child("edge").children():
            k = int(edge.value)
            if k not in seen:
                seen.add(k)
                todo.append(path + [k])
    raise RuntimeError("Fleta route has no path to end")


class Migration:
    def __init__(self):
        self.outputs = {}
        self.approved = {}
        self.xml_approved = {}
        self.preimages = {}
        self.canvas_count = 0
        self.map_data = {}
        self.bgms = {}
        for mid in MAP_IDS:
            src = a.load_image(a.SOURCE / f"Map/Map/Map9/{mid}.img", a.BMS_KEY)
            bgm = str(a.child_value(src.root.child("info"), "bgm") or "")
            if bgm:
                pack, track = bgm.split("/", 1)
                self.bgms.setdefault(pack, set()).add(track)

    def put(self, relative, data):
        if relative not in self.preimages:
            target = ROOT / relative
            self.preimages[relative] = sha(target.read_bytes()) if target.exists() else None
        self.outputs[relative] = data if isinstance(data, bytes) else data.encode("utf-8")

    def img(self, relative, image, xml=None):
        data = a.encode_image_body(image, a.gms_reader())
        self.put(relative, data)
        if xml:
            self.put(xml, a.image_to_xml(image, Path(relative).name))

    def validate_img(self, relative, data, approved=None):
        im = a.WzImage.from_bytes(data, key=a.GMS_KEY, name=relative)
        im.parse()
        if im.truncated or im.parse_warnings:
            raise RuntimeError(f"invalid {relative}: {im.parse_warnings}")
        for n, p in a.walk(im.root):
            if approved and not any(tuple(p.split("/"))[:len(r)] == r for r in approved):
                continue
            if isinstance(n, a.WzCanvasProperty):
                if (n.format, n.format2) != (1, 0):
                    raise RuntimeError(f"Canvas format: {relative}:{p}")
                bm = decode_4444(n)
                if bm is None or (bm.getbbox() is None and max(n.width, n.height) > 1):
                    raise RuntimeError(f"invisible Canvas: {relative}:{p}")
                self.canvas_count += 1
            if isinstance(n, a.WzUolProperty) and n.parent.get(str(n.value)) is None:
                raise RuntimeError(f"unresolved UOL: {relative}:{p}")
        return im

    def insert(self, relative, parent, props, xmls=()):
        baseline = BASE / relative
        current = ROOT / relative
        before = baseline.read_bytes() if baseline.exists() else current.read_bytes()
        im = a.WzImage.from_bytes(before, key=a.GMS_KEY)
        im.parse()
        node = im.root.get("/".join(parent)) if parent else im.root
        if node is None:
            raise RuntimeError(f"missing insertion parent {relative}:{parent}")
        if any(node.child(p.name) is not None for p in props):
            raise RuntimeError(f"Seed ID collides in baseline: {relative}")
        anchor = node.children()[-1].name
        result = a.insert_property_records_before(before, parent, props, anchor)
        approved = {(*parent, p.name) for p in props}
        a.verify_raw_record_insert_scope(before, result, approved)
        self.validate_img(relative, result, approved)
        self.approved[relative] = [list(x) for x in sorted(approved)]
        self.put(relative, result)
        for relative_xml in xmls:
            b = BASE / relative_xml
            text = (b if b.exists() else ROOT / relative_xml).read_text(encoding="utf-8")
            old = ET.fromstring(text)
            par = old
            for key in parent:
                par = next(c for c in par if c.get("name") == key)
            xml_anchor = list(par)[-1].get("name")
            result_text = a.insert_xml_properties_before(text, parent, props, xml_anchor)
            # Verify old sibling XML semantics and order exactly.
            new = ET.fromstring(result_text)
            par_new = new
            for key in parent:
                par_new = next(c for c in par_new if c.get("name") == key)
            added = {p.name for p in props}
            retained = [ET.tostring(c) for c in par_new if c.get("name") not in added]
            if retained != [ET.tostring(c) for c in par]:
                raise RuntimeError(f"protected XML changed {relative_xml}")
            self.xml_approved[relative_xml] = (parent, {p.name for p in props})
            self.put(relative_xml, result_text)

    def maps(self):
        for mid in MAP_IDS:
            print(f"Project map {mid}", flush=True)
            path = a.SOURCE / f"Map/Map/Map9/{mid}.img"
            src = a.load_image(path, a.BMS_KEY)
            f = (mid - 992000000) // 1000
            self.map_data[str(f)] = {
                "portals": {a.child_value(n, "pn"): [a.child_value(n, "x"), a.child_value(n, "y"),
                    str(a.child_value(n, "script") or ""), str(a.child_value(n, "tn") or "")]
                    for n in src.root.child("portal").children()},
                "spawns": [[int(a.child_value(n, "id")), int(a.child_value(n, "x")), int(a.child_value(n, "cy"))]
                    for n in src.root.child("life").children() if a.child_value(n, "type") == "m"],
            }
            if f == 19:
                self.map_data[str(f)]["route"] = route_from(src.root)
            im = projection(path, lambda root: sanitize_map(root, mid))
            self.redirect_assets(im)
            bgm = str(a.child_value(im.root.child("info"), "bgm") or "")
            if bgm:
                pack, track = bgm.split("/", 1)
                existing = ROOT / f"clien/Data/Sound/{pack}.img"
                if not existing.exists() or a.load_image(existing, a.GMS_KEY).root.get(track) is None:
                    dest = f"clien/Data/Sound/seed{pack}.img"
                    if dest not in self.outputs:
                        # All needed tracks in this source pack; no existing sound file changed.
                        sound = fresh(f"seed{pack}.img")
                        source = a.load_image(a.SOURCE / f"Sound/{pack}.img", a.BMS_KEY)
                        header = a.load_image(ROOT / "clien/Data/Sound/Bgm12.img", a.GMS_KEY).root.get("AquaCave").header
                        for track_name in sorted(self.bgms[pack]):
                            node = source.root.get(track_name)
                            if not isinstance(node, a.WzSoundProperty):
                                raise RuntimeError(f"missing BGM {pack}/{track_name}")
                            sound.root.add(a.clone_sound(node, None, bytes(header)))
                        self.img(dest, sound)
                    a.set_string(im.root.child("info"), "bgm", f"seed{pack}/{track}")
            self.img(f"clien/Data/Map/Map/Map9/{mid}.img", im,
                     f"gms-server/wz/Map.wz/Map/Map9/{mid}.img.xml")

    def redirect_assets(self, im):
        refs = []
        for n in im.root.child("back").children():
            branch = "ani" if a.child_value(n, "ani") else "back"
            refs.append((n, "bS", "Back", f"{branch}/{a.child_value(n, 'no')}"))
        for layer in [c for c in im.root.children() if c.name.isdigit()]:
            for n in layer.child("obj").children() if layer.child("obj") else []:
                refs.append((n, "oS", "Obj", "/".join(str(a.child_value(n, k)) for k in ["l0", "l1", "l2"])))
            info = layer.child("info")
            if info and a.child_value(info, "tS"):
                paths = [f"{a.child_value(n, 'u')}/{a.child_value(n, 'no')}" for n in layer.child("tile").children()]
                refs.append((info, "tS", "Tile", paths))
        for n, field, kind, branches in refs:
            name = str(a.child_value(n, field))
            if not name:
                continue
            branches = branches if isinstance(branches, list) else [branches]
            existing = ROOT / f"clien/Data/Map/{kind}/{name}.img"
            if existing.exists() and all(a.load_image(existing, a.GMS_KEY).root.get(p) is not None for p in branches):
                continue
            dest = f"clien/Data/Map/{kind}/seed{name}.img"
            source_path = a.SOURCE / f"Map/{kind}/{name}.img"
            source = a.load_image(source_path, a.BMS_KEY)
            if dest in self.outputs:
                out = a.WzImage.from_bytes(self.outputs[dest], key=a.GMS_KEY)
                out.parse()
            else:
                out = fresh(f"seed{name}.img")
            mat = a.CanvasMaterializer()
            mat.max_edge = 0
            for branch in sorted(set(branches)):
                if out.root.get(branch) is not None:
                    continue
                node = source.root.get(branch)
                if node is None:
                    raise RuntimeError(f"missing source asset {source_path}:{branch}")
                pieces = branch.split("/")
                parent = a.ensure_path(out.root, "/".join(pieces[:-1])) if len(pieces) > 1 else out.root
                parent.add(clone(node, source, source_path, mat))
            self.img(dest, out)
            a.set_string(n, field, "seed" + name)

    def mobs(self):
        for mid in sorted(MOBS):
            path = Path(f"/private/tmp/seed-tower-mobs/Mob_{mid}.img")
            if not path.exists():
                path = a.extract_mob(mid)
            def sanitize(root):
                info = root.child("info")
                a.sanitize_mob(root, mid)
                # Only legacy MobSkill IDs/levels already installed in this server.
                if mid == 9309201:
                    skills = a.WzSubProperty("skill")
                    for i, (skill, level, action) in enumerate([(105, 1, 1), (123, 1, 2)]):
                        skills.add(scalar_node(str(i), {"skill": skill, "level": level, "action": action}))
                    info.add(skills)
                for attack in [n for n in root.children() if n.name.startswith("attack")]:
                    ai = attack.child("info")
                    if ai:
                        for field in ["FSM", "fsm", "jumpAttack", "mobZone", "disease", "diseaseLevel"]:
                            a.remove_child(ai, field)
                        if ai.child("ball"):
                            a.set_int(ai, "type", 2)
                            a.set_int(ai, "bulletSpeed", 300)
                            if ai.child("hit"):
                                a.set_int(ai.child("hit"), "attach", 1)
                        if mid == 9309201:
                            a.set_int(ai, "disease", 125 if attack.name == "attack1" else 126)
                            a.set_int(ai, "level", 1)
                if mid in {9309116, 9309117}:
                    a.set_int(info, "maxHP", 1)
                    a.set_int(info, "eva", 0)
                    a.set_int(info, "flySpeed", 60)
                if mid == 9309123:
                    a.set_int(info, "maxHP", 100000)
                    a.set_int(info, "damagedByMob", 1)
                    a.set_int(info, "bodyAttack", 0)
            im = projection(path, sanitize)
            link = a.child_value(im.root.child("info"), "link")
            if link and not (ROOT / f"clien/Data/Mob/{int(link):07d}.img").exists() and int(link) not in MOBS:
                raise RuntimeError(f"uninstalled mob link {mid}->{link}")
            self.img(f"clien/Data/Mob/{mid:07d}.img", im, f"gms-server/wz/Mob.wz/{mid:07d}.img.xml")

    def reactors(self):
        for rid in sorted(REACTORS):
            def sanitize(root):
                a.set_string(root, "action", "seedCoconut" if rid >= 9921000 else "seedSeal")
                if rid < 9921000:
                    for state in [c for c in root.children() if c.name.isdigit()]:
                        # Portals perform the card check; no legacy maze-key drop trigger.
                        state._children.pop("event", None)
                        event = a.WzSubProperty("event")
                        event.add(scalar_node("0", {"type": 999, "state": int(state.name)}))
                        state.add(event)
            im = projection(a.SOURCE / f"Reactor/{rid}.img", sanitize)
            self.img(f"clien/Data/Reactor/{rid}.img", im, f"gms-server/wz/Reactor.wz/{rid}.img.xml")

    def hazards(self):
        source_path = a.SOURCE / "Map/Obj/trap.img"
        source = a.load_image(source_path, a.BMS_KEY)
        names = a.load_image(a.SOURCE / "String/Mob.img", a.BMS_KEY)
        for mid in HAZARDS:
            if names.root.child(str(mid)):
                raise RuntimeError(f"hazard ID collides with TMS mob {mid}")
            im = fresh(f"{mid}.img")
            im.root.add(scalar_node("info", {"level": 1, "maxHP": 2147483647, "maxMP": 1,
                "PADamage": 0, "PDDamage": 0, "MADamage": 0, "MDDamage": 0,
                "acc": 0, "eva": 0, "exp": 0, "speed": 0, "flySpeed": 1,
                "boss": 1, "bodyAttack": 0, "firstAttack": 0, "hideHP": 1, "hideName": 1}))
            branch = source.root.get("fire/fireSteam/0" if mid == 9309400 else "stone/stoneDM/0")
            mat = a.CanvasMaterializer(); mat.max_edge = 0
            for action in ["stand", "fly", "hit1", "die1"]:
                frames = a.WzSubProperty(action)
                for frame in branch.children():
                    if not frame.name.isdigit():
                        continue
                    projected = clone(frame, source, source_path, mat)
                    if mid != 9309400:
                        # Color is the compatibility danger category; timing/geometry stay source-exact.
                        bitmap = decode_4444(projected)
                        pixels = np.array(bitmap)
                        light = pixels[:, :, :3].mean(axis=2).astype(np.uint8)
                        tint = np.array([70, 160, 255] if mid == 9309401 else [90, 225, 130], dtype=np.uint16)
                        pixels[:, :, :3] = (light[:, :, None].astype(np.uint16)*tint//255).astype(np.uint8)
                        projected._png_data = a.encode_canvas_payload(Image.fromarray(pixels), 1,
                            projected.width, projected.height, key=a.GMS_KEY, listwz=False, zlib_level=6)
                        projected._png_length = len(projected._png_data)
                    frames.add(projected)
                im.root.add(frames)
            self.img(f"clien/Data/Mob/{mid}.img", im, f"gms-server/wz/Mob.wz/{mid}.img.xml")

    def strings(self, name, props, parent=()):
        self.insert(f"clien/Data/String/{name}.img", parent, props,
                    [f"gms-server/{tree}/String.wz/{name}.img.xml" for tree in ["wz", "wz-zh-CN"]])

    def entities(self):
        im = projection(a.SOURCE / "Npc/2540000.img", a.sanitize_npc)
        self.img("clien/Data/Npc/2540000.img", im, "gms-server/wz/Npc.wz/2540000.img.xml")
        self.strings("Npc", [scalar_node("2540000", {"name": "艾丽西亚", "func": "起源之塔"})])
        src = a.load_image(a.SOURCE / "String/Mob.img", a.BMS_KEY)
        self.strings("Mob", [scalar_node(str(mid), {"name": HAZARDS[mid] if mid in HAZARDS else a.child_value(src.root.child(str(mid)), "name") or "起源之塔怪物"}) for mid in sorted(MOBS | set(HAZARDS))])
        self.strings("Map", [scalar_node(str(mid), {"mapName": "起源之塔大厅" if mid == MAP_IDS[0] else f"起源之塔 {(mid-MAP_IDS[0])//1000} 层", "streetName": "起源之塔"}) for mid in MAP_IDS], ("etc",))
        helper = a.load_image(a.SOURCE / "Map/MapHelper.img", a.BMS_KEY)
        mat = a.CanvasMaterializer(); mat.max_edge = 0
        prop = clone(helper.root.get("mark/aquarisTower"), helper, a.SOURCE / "Map/MapHelper.img", mat)
        self.insert("clien/Data/Map/MapHelper.img", ("mark",), [prop])

    def items(self):
        path = a.SOURCE / "Item/Etc/0400.img"
        source = a.load_image(path, a.BMS_KEY)
        names = {4000968: "椰子果", 4009237: "古代蓝乌龟蛋", 4009238: "古代橙乌龟蛋", 4009497: "金乌龟蛋"}
        mat = a.CanvasMaterializer(); mat.max_edge = 0
        props = []
        string_props = []
        for iid in ITEMS:
            if iid < 4009900:
                node = clone(source.root.child("0"+str(iid)), source, path, mat)
                info = node.child("info")
                for field in ["lv", "autoPrice", "quest", "questId"]:
                    a.remove_child(info, field)
                a.set_int(info, "tradeBlock", 1); a.set_int(info, "notSale", 1)
                a.set_int(info, "slotMax", 3000); a.set_int(info, "price", 1)
                desc = "起源之塔内收集，离开时回收。"
            else:
                index = iid - 4009900
                color, rank = (index // 7, index % 7 + 1) if index < 28 else (4, 0)
                names[iid] = (COLORS[color] + f"色数字卡 {rank}") if color < 4 else "紫色万能卡"
                desc = "在同色石碑按上，数字必须严格大于石碑；紫卡可解任意石碑。"
                node = a.WzSubProperty("0"+str(iid))
                info = scalar_node("info", {"slotMax": 3000, "price": 1, "tradeBlock": 1, "notSale": 1})
                # Modern field cards become inventory items using the actual seal artwork.
                card_path = a.SOURCE / f"Reactor/{9260004 + min(color, 3)}.img"
                card_source = a.load_image(card_path, a.BMS_KEY)
                frame = clone(card_source.root.get(f"{rank-1 if rank else 7}/0"), card_source, card_path, mat)
                card_bitmap = decode_4444(frame)
                card_bitmap.thumbnail((32, 32), Image.Resampling.LANCZOS)
                bitmap = Image.new("RGBA", (32, 32))
                bitmap.alpha_composite(card_bitmap, ((32-card_bitmap.width)//2, 32-card_bitmap.height))
                for icon_name in ["icon", "iconRaw"]:
                    icon = a.WzCanvasProperty(icon_name)
                    icon.width = icon.height = 32; icon.format = 1; icon.format2 = 0
                    icon._png_data = a.encode_canvas_payload(bitmap, 1, 32, 32, key=a.GMS_KEY, listwz=False, zlib_level=6)
                    icon._png_length = len(icon._png_data); icon._png_offset = 0
                    icon.add(a.WzVectorProperty("origin", 0, 32))
                    info.add(icon)
                node.add(info)
            props.append(node)
            string_props.append(scalar_node(str(iid), {"name": names[iid], "desc": desc}))
        # Reserved cards must be absent in the modern source as well.
        for iid in range(4009900, 4009929):
            if source.root.child("0"+str(iid)) is not None:
                raise RuntimeError(f"source item ID collision {iid}")
        self.insert("clien/Data/Item/Etc/0400.img", (), props, ["gms-server/wz/Item.wz/Etc/0400.img.xml"])
        self.strings("Etc", string_props, ("Etc",))

    def run(self):
        self.maps(); self.mobs(); self.hazards(); self.reactors(); self.entities(); self.items()
        for relative, data in self.outputs.items():
            if relative.endswith(".xml"):
                ET.fromstring(data)
            if relative.endswith(".img"):
                print(f"Validate {relative}", flush=True)
                roots = {tuple(p) for p in self.approved.get(relative, [])}
                self.validate_img(relative, data, roots or None)
        return self.outputs

    def install(self):
        # Check every target before committing any file, including resumed installs.
        for relative, data in self.outputs.items():
            target = ROOT / relative
            actual = sha(target.read_bytes()) if target.exists() else None
            if actual != self.preimages[relative]:
                raise RuntimeError(f"target changed during generation {relative}")
            if not target.exists() or target.read_bytes() == data:
                continue
            if relative in self.approved:
                a.verify_raw_record_insert_scope(target.read_bytes(), data,
                    {tuple(p) for p in self.approved[relative]})
            elif relative in self.xml_approved:
                parent, ids = self.xml_approved[relative]
                protected = []
                for payload in [target.read_bytes(), data]:
                    root = ET.fromstring(payload)
                    node = root
                    for name in parent:
                        node = next(c for c in node if c.get("name") == name)
                    for child in list(node):
                        if child.get("name") in ids:
                            node.remove(child)
                    protected.append(ET.tostring(root))
                if protected[0] != protected[1]:
                    raise RuntimeError(f"current protected XML changed {relative}")
            else:
                raise RuntimeError(f"refuse full rewrite of existing standalone {relative}")
        for relative, data in self.outputs.items():
            target = ROOT / relative
            if target.exists() and target.read_bytes() == data:
                continue
            if target.exists() and not (BASE / relative).exists():
                a.atomic_write_bytes(BASE / relative, target.read_bytes())
            a.atomic_write_bytes(target, data)
        # Update only the generated metadata block of our new event script.
        event = ROOT / "gms-server/scripts/event/SeedTower20.js"
        text = event.read_text(encoding="utf-8")
        localized_event = ROOT / "gms-server/scripts-zh-CN/event/SeedTower20.js"
        if localized_event.exists() and localized_event.read_text(encoding="utf-8") != text:
            raise RuntimeError("Seed event language copies differ; reconcile before generation")
        start, end = "// BEGIN SEED DATA", "// END SEED DATA"
        left, rest = text.split(start, 1); _, right = rest.split(end, 1)
        generated = "\nvar SEED_DATA = " + json.dumps(self.map_data, ensure_ascii=False, separators=(",", ":")) + ";\n"
        event_text = left + start + generated + end + right
        a.atomic_write_text(event, event_text)
        a.atomic_write_text(localized_event, event_text)
        manifest = {"canvas_decodes": self.canvas_count, "raw_insert_roots": self.approved,
                    "files": {r: sha(b) for r, b in sorted(self.outputs.items())},
                    "baseline": {r: sha((BASE/r).read_bytes()) for r in self.outputs if (BASE/r).exists()}}
        a.atomic_write_text(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    migration = Migration()
    outputs = migration.run()
    print(f"Validated {len(outputs)} files, {migration.canvas_count} Canvas decodes")
    if args.install:
        migration.install()
        print("Installed deterministic Seed projections and raw insertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
