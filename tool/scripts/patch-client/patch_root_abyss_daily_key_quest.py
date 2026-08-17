#!/usr/bin/env python3
"""Patch Root Abyss daily key quest resources and gate checks."""

from __future__ import annotations

import base64
import io
import re
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tool/wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzStringProperty,
    WzSubProperty,
    WzVectorProperty,
)
from wzpy.canvas import decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.writer import encode_image_body  # noqa: E402


QUEST_ID = 30027
KEY_ITEM_ID = 5689103
KEY_NODE = f"0{KEY_ITEM_ID}"
KEY_ICON = Path("/Users/lizixian/Downloads/5689103.png")
TARGET_KEY = WzKey.for_region("GMS")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def replace_imgdir_block(text: str, name: str, replacement: str) -> str:
    marker = f'<imgdir name="{name}">'
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"missing block {name}")
    pos = start
    depth = 0
    while pos < len(text):
        next_open = text.find("<imgdir", pos)
        next_close = text.find("</imgdir>", pos)
        if next_close < 0:
            raise RuntimeError(f"unterminated block {name}")
        if 0 <= next_open < next_close:
            open_end = text.find(">", next_open)
            if open_end < 0:
                raise RuntimeError(f"unterminated imgdir opener in block {name}")
            if text[open_end - 1] != "/":
                depth += 1
            pos = open_end + 1
        else:
            depth -= 1
            pos = next_close + len("</imgdir>")
            if depth == 0:
                return text[:start] + replacement + text[pos:]
    raise RuntimeError(f"unterminated block {name}")


def patch_quest_wz_xml() -> None:
    check = ROOT / "gms-server/wz/Quest.wz/Check.img.xml"
    act = ROOT / "gms-server/wz/Quest.wz/Act.img.xml"
    check_block = '''<imgdir name="30027">
    <imgdir name="0">
      <int name="npc" value="1064002" />
      <int name="lvmin" value="125" />
      <int name="interval" value="1440" />
      <string name="startscript" value="q30027s" />
      <imgdir name="quest">
        <imgdir name="0">
          <int name="id" value="30013" />
          <int name="state" value="2" />
          <int name="order" value="1" />
        </imgdir>
      </imgdir>
      <int name="dayByDay" value="1" />
    </imgdir>
    <imgdir name="1">
      <int name="npc" value="1064002" />
      <string name="endscript" value="q30027e" />
      <int name="order" value="1" />
      <imgdir name="mob">
        <imgdir name="0">
          <int name="id" value="7120110" />
          <int name="count" value="100" />
          <int name="order" value="1" />
        </imgdir>
        <imgdir name="1">
          <int name="id" value="7120112" />
          <int name="count" value="100" />
          <int name="order" value="2" />
        </imgdir>
      </imgdir>
    </imgdir>
  </imgdir>'''
    act_block = '''<imgdir name="30027">
    <imgdir name="0" />
    <imgdir name="1">
      <imgdir name="item">
        <imgdir name="0">
          <int name="id" value="5689103" />
          <int name="count" value="12" />
          <int name="order" value="1" />
        </imgdir>
      </imgdir>
    </imgdir>
  </imgdir>'''
    atomic_write_text(check, replace_imgdir_block(check.read_text(encoding="utf-8"), "30027", check_block))
    atomic_write_text(act, replace_imgdir_block(act.read_text(encoding="utf-8"), "30027", act_block))


def patch_server_string_cash() -> None:
    path = ROOT / "gms-server/wz/String.wz/Cash.img.xml"
    text = path.read_text(encoding="utf-8")
    block = f'<imgdir name="{KEY_ITEM_ID}"><string name="name" value="魔盒钥匙"/><string name="desc" value="通往深渊的钥匙。"/></imgdir>'
    if f'<imgdir name="{KEY_ITEM_ID}">' in text:
        text = replace_imgdir_block(text, str(KEY_ITEM_ID), block)
    else:
        pos = text.rfind("</imgdir>")
        if pos < 0:
            raise RuntimeError(f"missing root close in {path}")
        text = text[:pos] + block + text[pos:]
    atomic_write_text(path, text)


def icon_canvases() -> tuple[WzCanvasProperty, WzCanvasProperty]:
    image = Image.open(KEY_ICON).convert("RGBA")
    canvases = []
    for name in ("icon", "iconRaw"):
        canvas = WzCanvasProperty(name)
        canvas.width, canvas.height = image.size
        canvas.format = 1
        canvas.format2 = 0
        canvas._png_data = encode_canvas_payload(image, 1, image.width, image.height, key=TARGET_KEY, listwz=False)
        canvas._png_length = len(canvas._png_data)
        canvas.add(WzVectorProperty("origin", 0, image.height, canvas))
        canvases.append(canvas)
    return canvases[0], canvases[1]


def patch_client_cash_item() -> None:
    template_path = ROOT / "clien/Data/Item/Cash/0561.img"
    image = WzImage.from_bytes(template_path.read_bytes(), key=TARGET_KEY, name="0568.img")
    image.parse()
    image.root._children.clear()

    item = WzSubProperty(KEY_NODE, image.root)
    info = WzSubProperty("info", item)
    icon, icon_raw = icon_canvases()
    info.add(icon)
    info.add(icon_raw)
    info.add(WzIntProperty("cash", 1, info))
    item.add(info)
    image.root.add(item)

    out = ROOT / "clien/Data/Item/Cash/0568.img"
    atomic_write(out, encode_image_body(image, image.wz_file.reader))
    verify = WzImage.from_bytes(out.read_bytes(), key=TARGET_KEY, name=out.name)
    verify.parse()
    for path in (f"{KEY_NODE}/info/icon", f"{KEY_NODE}/info/iconRaw"):
        canvas = verify.root.get(path)
        if not isinstance(canvas, WzCanvasProperty):
            raise RuntimeError(f"missing {path}")
        decoded = decode_canvas(canvas, region="GMS")
        if decoded.getbbox() is None:
            raise RuntimeError(f"blank {path}")


def patch_server_cash_item_xml() -> None:
    raw = base64.b64encode(KEY_ICON.read_bytes()).decode("ascii")
    path = ROOT / "gms-server/wz/Item.wz/Cash/0568.img.xml"
    text = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<imgdir name="0568.img">
  <imgdir name="{KEY_NODE}">
    <imgdir name="info">
      <canvas name="icon" width="33" height="32" basedata="{raw}">
        <vector name="origin" x="0" y="32" />
      </canvas>
      <canvas name="iconRaw" width="33" height="32" basedata="{raw}">
        <vector name="origin" x="0" y="32" />
      </canvas>
      <int name="cash" value="1" />
    </imgdir>
  </imgdir>
</imgdir>
'''
    atomic_write_text(path, text)


def patch_client_string_cash() -> None:
    path = ROOT / "clien/Data/String/Cash.img"
    image = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(f"malformed {path}: {image.parse_warnings}")
    node = image.root.child(str(KEY_ITEM_ID))
    if not isinstance(node, WzSubProperty):
        node = WzSubProperty(str(KEY_ITEM_ID), image.root)
        image.root.add(node)
    node._children.clear()
    node.add(WzStringProperty("name", "魔盒钥匙", node))
    node.add(WzStringProperty("desc", "通往深渊的钥匙。", node))
    atomic_write(path, encode_image_body(image, image.wz_file.reader))
    verify = WzImage.from_bytes(path.read_bytes(), key=TARGET_KEY, name=path.name)
    verify.parse()
    if verify.root.get(f"{KEY_ITEM_ID}/name") is None or verify.root.get(f"{KEY_ITEM_ID}/desc") is None:
        raise RuntimeError("failed to write String/Cash key text")


QUEST_SCRIPT = '''var status = -1;
var QUEST_ID = 30027;
var KEY_ITEM = 5689103;
var KEY_COUNT = 12;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        if (qm.getQuestStatus(QUEST_ID) == 2) {
            qm.sendOk("请明天再来。");
            qm.dispose();
            return;
        }
        qm.sendAcceptDecline("要开始执行鲁塔比斯每日任务吗？\\r\\n\\r\\n普通走廊和进阶走廊的怪物各消灭 #b100#k 只，就能获得 #b12#k 把 #v" + KEY_ITEM + "##t" + KEY_ITEM + "#。");
    } else if (status == 1) {
        qm.forceStartQuest(QUEST_ID);
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        qm.sendAcceptDecline("要完成这个鲁塔比斯每日任务吗？\\r\\n奖励：#b" + KEY_COUNT + "#k 把 #v" + KEY_ITEM + "##t" + KEY_ITEM + "#。");
    } else if (status == 1) {
        if (!qm.canHold(KEY_ITEM, KEY_COUNT)) {
            qm.sendOk("背包空间不足。");
            qm.dispose();
            return;
        }
        qm.gainItem(KEY_ITEM, KEY_COUNT);
        qm.forceCompleteQuest(QUEST_ID);
        qm.dispose();
    }
}
'''

NPC_SCRIPT = '''var status = -1;
var QUEST_ID = 30027;
var KEY_ITEM = 5689103;
var KEY_COUNT = 12;
var NORMAL_MOB = 7120110;
var ADVANCED_MOB = 7120112;
var NEED_COUNT = 100;

function progress(mobId) {
    var count = cm.getQuestProgressInt(QUEST_ID, mobId);
    if (count < 0) {
        return 0;
    }
    return count > NEED_COUNT ? NEED_COUNT : count;
}

function canCompleteDaily() {
    return progress(NORMAL_MOB) >= NEED_COUNT && progress(ADVANCED_MOB) >= NEED_COUNT;
}

function progressText() {
    return "当前进度：\\r\\n"
        + "普通走廊怪物：#b" + progress(NORMAL_MOB) + "#k / " + NEED_COUNT + "\\r\\n"
        + "进阶走廊怪物：#b" + progress(ADVANCED_MOB) + "#k / " + NEED_COUNT;
}

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == -1) {
        cm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }

    var questStatus = cm.getQuestStatus(QUEST_ID);
    if (status == 0) {
        if (questStatus == 0) {
            cm.sendAcceptDecline("要开始执行鲁塔比斯每日任务吗？\\r\\n\\r\\n普通走廊和进阶走廊的怪物各消灭 #b100#k 只，就能获得 #b12#k 把 #v" + KEY_ITEM + "##t" + KEY_ITEM + "#。");
            return;
        }
        if (questStatus == 1) {
            if (canCompleteDaily()) {
                cm.sendAcceptDecline("要完成这个鲁塔比斯每日任务吗？\\r\\n奖励：#b" + KEY_COUNT + "#k 把 #v" + KEY_ITEM + "##t" + KEY_ITEM + "#。");
                return;
            }
            cm.sendOk(progressText());
            cm.dispose();
            return;
        }
        cm.sendOk("请明天再来。");
        cm.dispose();
        return;
    }

    if (status == 1) {
        if (questStatus == 0) {
            cm.forceStartQuest(QUEST_ID);
            cm.dispose();
            return;
        }
        if (questStatus == 1 && canCompleteDaily()) {
            if (!cm.canHold(KEY_ITEM, KEY_COUNT)) {
                cm.sendOk("背包空间不足。");
                cm.dispose();
                return;
            }
            cm.gainItem(KEY_ITEM, KEY_COUNT);
            cm.forceCompleteQuest(QUEST_ID);
            cm.dispose();
            return;
        }
    }
    cm.dispose();
}
'''


def patch_quest_scripts() -> None:
    for rel in ("gms-server/scripts/quest/30027.js", "gms-server/scripts-zh-CN/quest/30027.js"):
        atomic_write_text(ROOT / rel, QUEST_SCRIPT)
    for rel in ("gms-server/scripts/npc/1064031.js", "gms-server/scripts-zh-CN/npc/1064031.js"):
        atomic_write_text(ROOT / rel, NPC_SCRIPT)


ROOTA_NEXT = '''var KEY_ITEM = 5689103;

function enter(pi) {
    var targets = {
        105200100: 105200110,
        105200200: 105200210,
        105200300: 105200310,
        105200400: 105200410,
        105200500: 105200510,
        105200600: 105200610,
        105200700: 105200710,
        105200800: 105200810
    };
    var target = targets[pi.getMapId()];
    if (target == null) {
        return false;
    }
    if (!pi.haveItem(KEY_ITEM, 1)) {
        pi.getPlayer().dropMessage(5, "你没有我需要的东西。");
        return false;
    }
    pi.getPlayer().dropMessage(5, "进入鲁塔比斯 Boss 房间消耗了 1 把 #t" + KEY_ITEM + "#。");
    pi.gainItem(KEY_ITEM, -1);
    pi.playPortalSound();
    pi.warp(target, "sp");
    return true;
}
'''


def patch_portal_scripts() -> None:
    for rel in ("gms-server/scripts/portal/rootaNext.js", "gms-server/scripts-zh-CN/portal/rootaNext.js"):
        atomic_write_text(ROOT / rel, ROOTA_NEXT)


def patch_event_scripts() -> None:
    for rel in [
        "gms-server/scripts/event/VONBONBattle.js",
        "gms-server/scripts/event/PIERREBattle.js",
        "gms-server/scripts/event/CQBattle.js",
        "gms-server/scripts/event/VELLUMBattle.js",
        "gms-server/scripts-zh-CN/event/VONBONBattle.js",
        "gms-server/scripts-zh-CN/event/PIERREBattle.js",
        "gms-server/scripts-zh-CN/event/CQBattle.js",
        "gms-server/scripts-zh-CN/event/VELLUMBattle.js",
    ]:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if "var keyItem = 5689103;" not in text:
            text = text.replace("var eventTime = 120;\n", "var eventTime = 120;\nvar keyItem = 5689103;\n")
        old = '''function playerEntry(eim, player) {
    eim.dropMessage(5, "[远征队] " + player.getName() + " 已进入副本地图。");
    if (eim.getProperty("spawnFailed") == "1") {
        player.dropMessage(5, "鲁塔比斯 Boss 生成失败，已返回入口。请查看服务端日志。");
        player.changeMap(exitMap);
        return;
    }
    var map = eim.getMapInstance(entryMap);
    player.changeMap(map, map.getPortal(0));
}'''
        new = '''function playerEntry(eim, player) {
    eim.dropMessage(5, "[远征队] " + player.getName() + " 已进入副本地图。");
    if (eim.getProperty("spawnFailed") == "1") {
        player.dropMessage(5, "鲁塔比斯 Boss 生成失败，已返回入口。请查看服务端日志。");
        player.changeMap(exitMap);
        return;
    }
    if (!player.haveItem(keyItem, 1)) {
        player.dropMessage(5, "你没有我需要的东西。");
        player.changeMap(exitMap);
        return;
    }
    player.getAbstractPlayerInteraction().gainItem(keyItem, -1);
    var map = eim.getMapInstance(entryMap);
    player.changeMap(map, map.getPortal(0));
}'''
        if old not in text:
            raise RuntimeError(f"playerEntry shape changed: {rel}")
        text = text.replace(old, new)
        atomic_write_text(path, text)


def patch_npc_scripts() -> None:
    for rel in [
        "gms-server/scripts/npc/1064005.js",
        "gms-server/scripts/npc/1064006.js",
        "gms-server/scripts/npc/1064007.js",
        "gms-server/scripts/npc/1064008.js",
        "gms-server/scripts-zh-CN/npc/1064005.js",
        "gms-server/scripts-zh-CN/npc/1064006.js",
        "gms-server/scripts-zh-CN/npc/1064007.js",
        "gms-server/scripts-zh-CN/npc/1064008.js",
    ]:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        if "var keyItem = 5689103;" not in text:
            text = text.replace('var pendingDifficulty = "normal";\n', 'var pendingDifficulty = "normal";\nvar keyItem = 5689103;\n')
        text = text.replace(
            'cm.sendOk("远征队即将开始，当前难度：#b" + difficultyName(em.getProperty("rootAbyssDifficulty")) + "#k。");\n            status = 4;',
            'cm.sendYesNo("进入一次鲁塔比斯 Boss 房间需要消耗 #b1#k 把 #v" + keyItem + "##t" + keyItem + "#。是否进入？");\n            status = 4;'
        )
        text = text.replace(
            'em.setProperty("leader", player.getName());\n        em.setProperty("channel", player.getClient().getChannel());',
            'if (!cm.haveItem(keyItem, 1)) {\n            cm.sendOk("你没有我需要的东西。");\n            cm.dispose();\n            return;\n        }\n        em.setProperty("leader", player.getName());\n        em.setProperty("channel", player.getClient().getChannel());'
        )
        atomic_write_text(path, text)


def main() -> int:
    patch_quest_wz_xml()
    patch_server_string_cash()
    patch_client_cash_item()
    patch_server_cash_item_xml()
    patch_client_string_cash()
    patch_quest_scripts()
    patch_portal_scripts()
    patch_event_scripts()
    patch_npc_scripts()
    print("patched root abyss daily key quest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
