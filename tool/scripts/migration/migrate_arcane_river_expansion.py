#!/usr/bin/env python3
"""Migrate Reverse City, Sellas, and non-boss Tenebris fields from TMS.

The migration is intentionally whitelist based.  It materializes modern canvas
links, converts every imported bitmap to GMS ARGB4444, prunes unsupported map
features, and writes the client plus server data together. Existing shared IMG
files are changed only by raw property-record appends.
"""

from __future__ import annotations

import io
import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from xml.sax.saxutils import quoteattr

from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory-IMG/Data")
PACKS = Path("/Users/lizixian/Documents/mxd/TMS/MapleStory/Data/Packs")
MS_PROBE = Path(
    "/Users/lizixian/Documents/mxd/TMS/black_mage_report_tools/"
    "ms_probe/bin/Debug/net8.0/MSProbe.dll"
)
BACKUP_ROOT = Path("/private/tmp/arcane-river-expansion-backup")
MOB_CACHE = Path("/private/tmp/arcane-river-mob-cache")
sys.path.insert(0, str(ROOT / "tool" / "wz-python"))

from wzpy import (  # noqa: E402
    WzCanvasProperty,
    WzConvexProperty,
    WzDoubleProperty,
    WzFloatProperty,
    WzImage,
    WzIntProperty,
    WzKey,
    WzLongProperty,
    WzNullProperty,
    WzShortProperty,
    WzSoundProperty,
    WzStringProperty,
    WzSubProperty,
    WzUolProperty,
    WzVectorProperty,
)
from wzpy.canvas import _decompress, decode_canvas, encode_canvas_payload  # noqa: E402
from wzpy.incremental_img import (  # noqa: E402
    _apply_edits,
    _count_edit,
    _find_list,
    _record_bytes,
    _reference_edits,
    _size_edits,
    mutate_img,
    scan_img,
)
from wzpy.incremental_xml import mutate_xml, scan_xml  # noqa: E402
from wzpy.reader import WzBinaryReader  # noqa: E402
from wzpy.writer import _read_sound_payload, encode_image_body  # noqa: E402


BMS_KEY = WzKey.for_region("BMS")
GMS_KEY = WzKey.for_region("GMS")
MAX_CANVAS_EDGE = 2048

MAP_IDS = tuple(
    int(value)
    for value in """
450007170,
450016000,450016010,450016020,450016030,450016040,450016050,450016060,450016070,450016080,450016090,450016100,450016110,450016120,450016130,450016140,450016150,450016160,450016200,450016210,450016220,450016230,450016240,450016250,450016260,450016270,450016280,
450009000,450009050,450009100,450009101,450009110,450009120,450009130,450009140,450009150,450009160,450009200,450009201,450009210,450009220,450009230,450009240,450009250,450009260,450009300,450009310,450009320,450009330,450009340,450009350,450009360,
450011120,450011220,450011320,450011400,450011410,450011420,450011430,450011440,450011450,450011460,450011500,450011510,450011520,450011530,450011540,450011550,450011560,450011570,450011580,450011590,450011600,450011610,450011620,450011630,450011640,450011650,450011660,
450012000,450012010,450012020,450012030,450012040,450012100,450012110,450012120,450012130,450012300,450012310,450012320,450012330,450012340,450012350,450012360,450012370,450012380,450012400,450012410,450012420,450012430,450012440,450012450,450012460,450012470,
450014010,450014020,450014030,450014040,450014050,450014060,450014070,450014080,450014090,450014100,450014110,450014120,450014130,450014140,450014150,450014160,450014170,450014180,450014190,450014200,450014210,450014220,450014230,450014240,450014300,450014310,450014320,
""".replace("\n", "").split(",")
    if value
)
MAP_ID_SET = set(MAP_IDS)

BOSS_MAP_IDS = {
    450009400, 450009430, 450009450, 450009480, 450009500,
    450011990,
    450012200, 450012210, 450012250, 450012500, 450012600, 450012650,
}
PRESERVED_EXISTING_MAP_IDS = {450009301, *BOSS_MAP_IDS}
INSTALLED_ROUTE_MAP_IDS = {450007160, 450009301}

PRESERVED_FILE_SHA256 = {
    "clien/Data/Map/Map/Map4/450009301.img": "6419324fc56d0b054e62fd5098499f20fa452641379c05f67a0aae3b6901a551",
    "gms-server/wz/Map.wz/Map/Map4/450009301.img.xml": "6d839dee18a7fd93b6a287fc62dd2d80555d62240539976512a1e63bb250a7d4",
    "clien/Data/Map/Map/Map4/450009400.img": "7e0160cbdf83ac7fcfc30b4aab8b31395f93e62e4c7b0793a4d31ed5e57beb48",
    "gms-server/wz/Map.wz/Map/Map4/450009400.img.xml": "2ecc5440eabe83d6a7d4b4c4b061166ba250dc7d4fb3ba1886d0f6fce6439d7a",
    "clien/Data/Map/Map/Map4/450011990.img": "2602dea0efadaa8e47d80d40c2c6124647c19ba526534a1eca54e0b37601556a",
    "gms-server/wz/Map.wz/Map/Map4/450011990.img.xml": "b68c9c2b8caefadd2b1ab6366a035c1b3450f30de21df1a478015bc2890e1735",
    "clien/Data/Sound/Bgm49.img": "a665b56cb6711b26c35319b36f2502c3c28501aa6e773f5f45feefd4b0f28842",
}

# Each shared file must be either the reviewed pre-migration baseline or the
# exact completed result. This permits recovery after a partial run without
# accepting an unknown artifact as a patch base.
SHARED_FILE_STATES = {
    "clien/Data/Map/MapHelper.img": (
        "310c6df5e4f747b969b4f157690a6fb2adfdaf371b2111a45c376ba441a52021",
        "f6d033355b03e44642b1d046927f344e0d1e42018db0b6c6dee6e069e9e2c551",
        "e78b66855c14d8f771690a3ae6cccdb2879a0b23a6c21cd42660fb7a85be9a7e",
    ),
    "clien/Data/Map/Tile/allInvisibleTile.img": (
        "cb466f4dfb5c5d53c9ad02b0faeb6207fe038e6914efe660003463534ecb9024",
        "ac9a7d91e406a713f417e2ff4f34dc4d0f3d00e80b6b5fbda563c3e89511fd1c",
    ),
    "clien/Data/Mob/8645010.img": (
        "2e475a35f816de04128690ba5f56a59335fe2a0c7df99bd8d5aa44c8f27a955d",
        "58ddd293257a7cb90eda0189ef2d1b011cfc8ac9d62e2dcec865973e78b8261e",
    ),
    "clien/Data/Mob/8645012.img": (
        "7433d2d9e1b9ee34536f3d3bcca7def031254a4789f6ed40dc81d3c758c1a88b",
        "93ed4c1c2ae0b3314f667652a3020f1b74c338628907af1c2a5eaf7f2702b1e3",
    ),
    "clien/Data/Sound/Bgm48.img": (
        "c728c479ceb70360cdb1a0c9d08df1ad01d9bb689a8014e2d8b7742f02e6c134",
        "9b28b583be68fe0add2e69917d15bf19256a78e1d49e97626efce8e87ccd9a0e",
    ),
    "clien/Data/Sound/Bgm54.img": (
        "eaeebcde2ee8e0bc0b585e6ae518fcba6e6b5ba41d6b611daeb5cf73f976b444",
        "441ceb790e51765dfa12207c8b133d464125dee30986fa3d0bd27be58da99229",
    ),
    "clien/Data/String/Map.img": (
        "f313bd0d322fb4c771b87f9a771eaa477a201ecd2466b5f8b67d85a70c4d35dd",
        "0dde95757c1c9c498a851a4c077d9ea66c56e47ee116a2102e4ad6233b68fad5",
        "21ab7791d0ebd3da1871a11bee175b60494888eb31d5d5033b02f416ca6ea0ea",
    ),
    "clien/Data/String/Mob.img": (
        "153760f3640b001c1a2b8981125c8ceb4f11ac28c8e8e6f2fa916a12a806dfad",
        "1225ca199ab55affb5b3d9e8fd2f944f0fc6668ac22a63fb283e88a11a5b1963",
        "0122649211e8e69f1ca1c225c6334985bc49d4d8751692a26df42b28cd51945f",
    ),
    "clien/Data/String/Npc.img": (
        "f9caa55f2a90a3a229fbb19997479d3edf3821368524f03ae92771878e7d5db7",
        "ae207d1fd687374f405005a5ad06701a3a966711bea165ae4e42e588f1fef171",
        "1115191114582ff25d33797f68f8dbb288ceb16c0308eac53bc3851026ab11d1",
    ),
    "gms-server/wz/Mob.wz/8645010.img.xml": (
        "4eeb699b2775aa491e56551df7177582389fc4ce018d49caa0e00795f809a941",
        "ed0be2d673ade8690a0d5ac7bd97f48447069e582c6b3fe38307a03649d576eb",
    ),
    "gms-server/wz/Mob.wz/8645012.img.xml": (
        "82865d2b1a87ccc422ae322cad1f73ad93258850485b5e8af05b63505bf26e0b",
        "ce147e35d653644eb0d0900dc7532710e03ae6cca280ad46515819f79b16a691",
    ),
    "gms-server/wz/String.wz/Map.img.xml": (
        "fa18ba5f98af2babe2fb0a367188dc0f8b9190ca70f12bbc8c7d28859b499807",
        "561c6fb35ce3e9e209cc6c240cee2a080a58d672845c0df08ee1b1ef5ca08ca4",
        "a5e4f88b30c2b4a79d4f014b4301e8799702c21c5b4c9ee52fdbe0a8655b44f3",
    ),
    "gms-server/wz/String.wz/Mob.img.xml": (
        "a2fc330da59df2e72cb39acc79d9420b321c3ce71f629a37cfaa8bff763ffe83",
        "8dd9797cbb495ea3481fdea29c5c8a1bbd5c11082b90dff2b0bb0f9bed157946",
        "b3d6219f68448fa53740c08f44bb5a77612bdcb4cedb95dc9d3a7f49e36c7cb3",
    ),
    "gms-server/wz/String.wz/Npc.img.xml": (
        "3be86a9e890036d27b532040a245d62ad247cef6300c5bba4c77cda6eb9d32d5",
        "f4f2a74d1044f73774a6a26d3cdcfd4642c470be80bc41cb12a7190e345fbeba",
        "e4bab4a432ed59351df2a1bddc1a5cfecbf12fd30cb63588bbc749bfed7b7b97",
    ),
    "gms-server/wz-zh-CN/String.wz/Map.img.xml": (
        "f5320f063d512ab144656f604524f47c3da5085d1806452ec7df3ac840d8e441",
        "dd8affe44461d2fc8598aeb8bc404a7fbdee2a4f7c6c87be1ef2fa29bac6d7e6",
        "944ccc89c83f53aa6495c67ac32d7419b32f812b90b484dcf71b60445943eff9",
    ),
    "gms-server/wz-zh-CN/String.wz/Mob.img.xml": (
        "6f4f3d21d551a4d63417a9d480ffbb166462ca521cde39b6950565ba328ff506",
        "41792e45f0ca9eaeb3a503bf1833ed0924799ab096583d4627979989ed2da0c8",
        "4c141d9652a18873f4d78ce6ffaad805a404b6d7983945ce58445e40ac329d48",
    ),
    "gms-server/wz-zh-CN/String.wz/Npc.img.xml": (
        "8085a33bfeb6307a1cb498e7aac6b7c9c81d0653b1cc5fbc1476bb225cac179b",
        "a4b4e6743c7a0485485815d2eb43436e9df9b13e52ff5dcccbd2fcfad8ae1f9e",
        "d247c50fa775aa0a6e54dbb8149cee293ff2c9a25b3f4d08272506abd132aec5",
    ),
}

TOWN_BY_PREFIX = {
    "450007": 450007040,
    "450009": 450009100,
    "450011": 450011120,
    "450012": 450012000,
    "450014": 450014050,
    "450016": 450016000,
}
MAP_MARKS = {
    "esfera", "Sellas", "aliance", "moonBridge",
    "TheLabyrinthOfSuffering", "Limen", "Reverse_City",
}
NEW_STANDALONE_ASSETS = {
    ("Back", "BM1_1"), ("Back", "BM2_1"), ("Back", "BM2_2"),
    ("Back", "BM3_1"), ("Back", "BM3_3"),
    ("Back", "blackMagician_Base"), ("Back", "blackMagician_Base2"),
    ("Back", "sellas"),
    ("Obj", "BM3"), ("Obj", "blackMagician_Base"), ("Obj", "sellas"),
    ("Tile", "BM2_1"), ("Tile", "BM2_2"),
    ("Back", "ReverseCity"), ("Obj", "ReverseCity"),
}
REUSED_MOB_IDS = {8645010, 8645012}
MAP_ONLY_AB_TESTS: set[int] = set()
LEGACY_MEDIA_DISABLED_MAPS: set[int] = set()
LEGACY_CONNECT_FIRST_MAPS = set(MAP_IDS)
LEGACY_SWIM_MAPS: set[int] = set()
LEGACY_ZERO_FIELD_LIMIT_MAPS: set[int] = set()
LIFE_UNSUPPORTED_BY_MAP: dict[int, set[str]] = {}
FOOTHOLD_UNSUPPORTED_BY_MAP: dict[int, set[str]] = {}
LEGACY_ASSET_CHILD_RENAMES: dict[tuple[str, str, str], dict[str, str]] = {}
PINNED_CLIENT_MAP_SHA256: dict[int, str] = {}
PRESERVED_ARRIVAL_PORTALS: dict[int, set[str]] = {}
LEGACY_CAVE_COLLISION_PORTALS: dict[int, dict[str, tuple[int, str]]] = {}
LEGACY_CHUCHU_SKY_WHALE_PORTALS: dict[int, dict[str, tuple[int, int, int, int, int, str]]] = {}

# Modern script portals whose destination is proven by the reverse portal in
# the adjacent TMS field.  They become ordinary old-client doors.
LEGACY_CAVE_ROUTE_PORTALS = {
    450007170: {"east00": (450016280, "west00")},
    450016280: {"east00": (450016000, "west00")},
    450016210: {"east00": (450016220, "west00")},
    450009100: {"up00": (450009200, "down00")},
    450009200: {
        "down00": (450009100, "up00"),
        "up00": (450009300, "down00"),
    },
    450009300: {
        "down00": (450009200, "up00"),
        "up00": (450009301, "sp"),
    },
    450011120: {
        "east00": (450011400, "west00"),
        "outMaze": (450009300, "sp"),
    },
    450011220: {
        "east00": (450011540, "west00"),
        "west00": (450011120, "east00"),
        "south00": (450011590, "west00"),
    },
    450011320: {
        "west00": (450011220, "south00"),
        "inMaze": (450011600, "east00"),
    },
    450011420: {"east00": (450011430, "west00")},
    450011450: {"east00": (450011460, "west00")},
    450011460: {"east00": (450011500, "west00")},
    450011500: {"east00": (450011510, "west00")},
    450011510: {"west00": (450011500, "east00")},
    450011590: {"east00": (450011600, "east00")},
    450011660: {"west00": (450011320, "sp")},
    450012000: {"east00": (450012010, "west00")},
    450012010: {"east00": (450012100, "west00")},
    450012100: {"east00": (450012110, "west00")},
    450012110: {"east00": (450012120, "west00")},
    450012120: {"east00": (450012130, "west00")},
    450012320: {"east00": (450012400, "east01")},
    450014090: {"east00": (450014100, "west00")},
    450014130: {"east00": (450014140, "west00")},
    450014200: {"east00": (450014210, "west00")},
}

REMOVED_NPCS = {
    9000123, 9000124, 9000131, 9000132, 9010100, 9010106, 9010109,
    9010112, 9010113, 9063173, 9063313, 9063366, 9063620, 9063870,
    9070104, 9070105, 9201594, 9270343, 9310649, 9330072,
    9401686, 9401687, 9401704, 9401705, 9401706, 9401707, 9401708,
}

MAP_ROOTS = {
    "info", "back", "life", "reactor", "foothold",
    "ladderRope", "miniMap", "portal", *(str(index) for index in range(8)),
}
MAP_INFO_UNSUPPORTED = {
    "AmbientBGM", "AmbientBGMv", "ReviveCurFieldOfNoTransfer",
    "ReviveCurFieldOfNoTransferNotDamaged", "ReviveCurFieldOfNoTransferPoint",
    "barrierArc", "barrierAut", "consumeItemCoolTime", "fieldLimit2",
    "fieldScript", "fieldType", "largeSplit", "limitUpgradeItem",
    "limitUseShop", "lvLimit", "mode", "noChair", "noHekatonEffect",
    "onFirstUserEnter", "onUserEnter", "partyStandAlone", "qrLimit",
    "quarterView", "remoteEffect", "reviveCurField", "specialSound",
    "standAlone", "noMapCmd", "MRLeft", "MRTop", "MRRight", "MRBottom",
    "bgmSub", "footStepSound", "mirror_Bottom",
    "AFKmob", "HobbangKing", "MR", "bonusStageNoChangeBack",
    "individualHuntField", "individualHuntFieldServerType", "noBackOverlapped",
    "qrLimitState", "qrLimitState2", "ratemob", "towerChairEnable", "zeroSideOnly",
}
OBJ_UNSUPPORTED = {
    "SN0", "SN_count", "dynamic", "move", "name", "piece", "spineAni",
    "questex", "tags", "timeScale",
    "cantThrough", "fadeName", "fadeType", "groupName", "quest", "sideType",
}
BACK_UNSUPPORTED = {"backTags", "w", "wx", "wy", "spineAni", "flowX", "flowY"}
LIFE_UNSUPPORTED = {"hold", "nofoothold"}
PORTAL_UNSUPPORTED = {
    "delay", "hideTooltip", "onlyOnce", "hRange", "horizontalImpact", "vRange",
    "shownAtMinimap",
}
MOB_INFO_UNSUPPORTED = {
    "attack", "bodyDisease", "bodyDiseaseLevel", "category", "chaseEffect",
    "default", "defaultHP", "defaultMP", "delAtomOnDead", "explosiveReward",
    "finalmaxHP", "firstAttackRange", "ignoreFieldOut", "ignoreMovable",
    "ignoreMoveImpact", "isRemoteRange", "linkMob", "maxHPb", "mobZone",
    "passive", "publicReward", "showNotRemoteDam", "skill", "stalking",
    "trans", "useReaction", "revive",
    "mobJobCategory", "opacityLayer",
}
NPC_INFO_UNSUPPORTED = {"condition1", "miniMapType", "sayFlip"}
NPC_ROOT_UNSUPPORTED_PREFIX = "condition"
OLD_MOB_FIELDS = {
    "PADamage": 0,
    "PDDamage": 0,
    "MADamage": 0,
    "MDDamage": 0,
    "level": 1,
}
LEGACY_BALLISTIC_ATTACKS = {
    8641002: (1, 300),
    8642012: (2, 400),
    8642013: (2, 400),
    8642014: (2, 400),
    8642015: (2, 400),
    8642021: (2, 400),
    8642022: (2, 400),
    8642050: (1, 300),
    8644001: (1, 300),
    8644005: (1, 300),
    8644007: (2, 300),
    8644008: (1, 300),
    8644010: (1, 300),
    8644709: (1, None),
}


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_write_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", prefix=f".{path.name}.", dir=path.parent, delete=False
    ) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def backup(path: Path) -> None:
    if not path.exists():
        return
    relative = path.relative_to(ROOT)
    target = BACKUP_ROOT / relative
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def load_image(path: Path, key: WzKey) -> WzImage:
    image = WzImage.from_bytes(path.read_bytes(), key=key, name=path.name)
    image.parse()
    return image


def gms_reader() -> WzBinaryReader:
    return WzBinaryReader(io.BytesIO(b""), GMS_KEY)


def child_value(node, name: str):
    child = node.child(name) if node is not None else None
    return getattr(child, "value", None)


def remove_child(node, name: str) -> None:
    if node is not None:
        node._children.pop(name, None)


def set_int(node: WzSubProperty, name: str, value: int) -> None:
    remove_child(node, name)
    node.add(WzIntProperty(name, int(value), node))


def set_string(node: WzSubProperty, name: str, value: str) -> None:
    remove_child(node, name)
    node.add(WzStringProperty(name, str(value), node))


def legacy_rope_pieces(y1: int, y2: int) -> list[tuple[str, int]]:
    pieces = [("0", y1 - 1)]
    cursor = y1 + 24
    bottom_start = y2 - 32
    while bottom_start - cursor >= 120:
        pieces.append(("3", cursor + 60))
        cursor += 120
    while cursor < bottom_start:
        pieces.append(("1", cursor + 15))
        cursor += 30
    pieces.append(("2", y2 - 17))
    return pieces


def legacy_ladder_pieces(y1: int, y2: int) -> list[tuple[str, int]]:
    pieces = [("0", y1 - 6)]
    middle_y = y1 + 29
    while middle_y < y2 - 5:
        pieces.append(("1", middle_y))
        middle_y += 48
    pieces.append(("3", y2 - 22))
    return pieces


def next_numeric_child_name(node: WzSubProperty) -> int:
    return max((int(child.name) for child in node.children() if child.name.isdigit()), default=-1) + 1


def add_legacy_connect_object(
    objects: WzSubProperty,
    index: int,
    kind: str,
    piece: str,
    x: int,
    y: int,
    z: int = 3,
    f: int = 0,
    z_mass: int = 0,
) -> int:
    entry = WzSubProperty(str(index), objects)
    objects.add(entry)
    set_string(entry, "oS", "connect")
    set_string(entry, "l0", kind)
    set_string(entry, "l1", "0")
    set_string(entry, "l2", piece)
    set_int(entry, "x", x)
    set_int(entry, "y", y)
    set_int(entry, "z", z)
    set_int(entry, "f", f)
    set_int(entry, "zM", z_mass)
    return index + 1


def downgrade_connect_nodes(root: WzSubProperty) -> dict[str, int]:
    ladder_rope = root.child("ladderRope")
    collisions = list(ladder_rope.children()) if isinstance(ladder_rope, WzSubProperty) else []
    collision_data = [
        (
            "ladder" if int(child_value(entry, "l") or 0) else "rope",
            int(child_value(entry, "x")),
            int(child_value(entry, "y1")),
            int(child_value(entry, "y2")),
        )
        for entry in collisions
    ]
    decorative: list[tuple[str, str, str, int, int, int, int, int]] = []
    removed = 0
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        for entry in list(objects.children()):
            if child_value(entry, "oS") != "connect":
                continue
            kind = str(child_value(entry, "l0"))
            x, y = int(child_value(entry, "x")), int(child_value(entry, "y"))
            matched = any(
                collision_kind == kind
                and abs(collision_x - x) <= 5
                and y1 - 160 <= y <= y2 + 160
                for collision_kind, collision_x, y1, y2 in collision_data
            )
            if not matched:
                original_piece = str(child_value(entry, "l2") or "1")
                max_piece = 4
                piece = original_piece if original_piece.isdigit() and int(original_piece) <= max_piece else "1"
                decorative.append(
                    (
                        layer.name,
                        kind if kind in {"rope", "ladder"} else "rope",
                        piece,
                        x,
                        y,
                        int(child_value(entry, "z") or 3),
                        int(child_value(entry, "f") or 0),
                        int(child_value(entry, "zM") or 0),
                    )
                )
            remove_child(objects, entry.name)
            removed += 1

    generated = 0
    for collision in collisions:
        remove_child(collision, "piece")
        kind = "ladder" if int(child_value(collision, "l") or 0) else "rope"
        x = int(child_value(collision, "x"))
        y1, y2 = int(child_value(collision, "y1")), int(child_value(collision, "y2"))
        page = int(child_value(collision, "page"))
        layer = root.child(str(page))
        objects = layer.child("obj") if isinstance(layer, WzSubProperty) else None
        if not isinstance(objects, WzSubProperty):
            raise RuntimeError(f"missing object layer {page} for ladderRope/{collision.name}")
        index = next_numeric_child_name(objects)
        pieces = legacy_ladder_pieces(y1, y2) if kind == "ladder" else legacy_rope_pieces(y1, y2)
        for piece, y in pieces:
            index = add_legacy_connect_object(objects, index, kind, piece, x, y)
            generated += 1

    for page, kind, piece, x, y, z, f, z_mass in decorative:
        layer = root.child(page)
        objects = layer.child("obj") if isinstance(layer, WzSubProperty) else None
        if not isinstance(objects, WzSubProperty):
            raise RuntimeError(f"missing decorative connect object layer {page}")
        add_legacy_connect_object(
            objects, next_numeric_child_name(objects), kind, piece, x, y, z, f, z_mass
        )
        generated += 1
    return {
        "removed": removed,
        "generated": generated,
        "collisions": len(collisions),
        "decorative": len(decorative),
    }


def normalize_connect_object_order(root: WzSubProperty) -> int:
    """Keep legacy connect pieces before ordinary objects with dense indices."""
    changed = 0
    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if not isinstance(objects, WzSubProperty):
            continue
        entries = list(objects.children())
        connect = [entry for entry in entries if child_value(entry, "oS") == "connect"]
        if not connect:
            continue
        ordered = connect + [entry for entry in entries if child_value(entry, "oS") != "connect"]
        expected_names = [str(index) for index in range(len(ordered))]
        if ordered == entries and [entry.name for entry in entries] == expected_names:
            continue
        objects._children.clear()
        for index, entry in enumerate(ordered):
            entry.name = str(index)
            objects.add(entry)
        changed += 1
    return changed


def downgrade_portal_types(root: WzSubProperty) -> int:
    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return 0
    changed = 0
    for entry in portal.children():
        if int(child_value(entry, "pt") or 0) == 10:
            set_int(entry, "pt", 3)
            changed += 1
    return changed


def walk(node, path: str = ""):
    yield node, path
    if hasattr(node, "children"):
        for child in node.children():
            child_path = f"{path}/{child.name}" if path else child.name
            yield from walk(child, child_path)


def decode_source_canvas(canvas: WzCanvasProperty) -> Image.Image:
    if int(canvas.format) + int(canvas.format2) != 4098:
        return decode_canvas(canvas, region="BMS").convert("RGBA")
    raw = _decompress(canvas, BMS_KEY)
    width, height = int(canvas.width), int(canvas.height)
    linear_size = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(raw) < linear_size:
        raise RuntimeError(f"short BC7 payload: {len(raw)} < {linear_size}")
    header = struct.pack(
        "<I6I11I", 124, 0x00081007, height, width, linear_size, 0, 0, *([0] * 11)
    )
    pixel_format = struct.pack("<II4s5I", 32, 4, b"DX10", 0, 0, 0, 0, 0)
    caps = struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    dx10 = struct.pack("<5I", 98, 3, 0, 1, 0)
    with Image.open(io.BytesIO(b"DDS " + header + pixel_format + caps + dx10 + raw[:linear_size])) as decoded:
        return decoded.convert("RGBA")


class CanvasMaterializer:
    def __init__(self) -> None:
        self.images: dict[Path, WzImage] = {}
        self.decoded: dict[tuple[Path, str], Image.Image] = {}
        self.canvases = 0
        self.links = 0
        self.resized = 0

    def source_image(self, path: Path) -> WzImage:
        path = path.resolve()
        if path not in self.images:
            if not path.exists():
                raise FileNotFoundError(f"linked IMG does not exist: {path}")
            self.images[path] = load_image(path, BMS_KEY)
        return self.images[path]

    def external_target(self, value: str) -> tuple[Path, str]:
        normalized = value.replace("\\", "/").removeprefix("Data/").lstrip("/")
        marker = ".img/"
        if marker not in normalized:
            raise RuntimeError(f"invalid _outlink: {value}")
        file_part, property_path = normalized.split(marker, 1)
        return SOURCE / f"{file_part}.img", property_path

    def resolve_canvas(
        self, canvas: WzCanvasProperty, image: WzImage, image_path: Path, seen: set[tuple[Path, str]]
    ) -> tuple[WzCanvasProperty, WzImage, Path, str]:
        outlink = canvas.child("_outlink")
        inlink = canvas.child("_inlink")
        if outlink is not None:
            target_path, property_path = self.external_target(str(outlink.value))
            target_image = self.source_image(target_path)
            target = target_image.root.get(property_path)
            self.links += 1
        elif inlink is not None:
            target_path, property_path, target_image = image_path, str(inlink.value).lstrip("/"), image
            target = image.root.get(property_path)
            self.links += 1
        elif canvas.has_pixels():
            return canvas, image, image_path, ""
        else:
            raise RuntimeError(f"canvas without pixels or link in {image_path}: {canvas.name}")
        identity = (target_path.resolve(), property_path)
        if identity in seen:
            raise RuntimeError(f"cyclic canvas link: {target_path}:{property_path}")
        if not isinstance(target, WzCanvasProperty):
            raise RuntimeError(f"unresolved canvas link: {target_path}:{property_path}")
        if target.has_pixels():
            return target, target_image, target_path, property_path
        return self.resolve_canvas(target, target_image, target_path, seen | {identity})

    def materialize(
        self, source: WzCanvasProperty, parent, image: WzImage, image_path: Path
    ) -> WzCanvasProperty:
        pixel_source, pixel_image, pixel_path, pixel_property = self.resolve_canvas(
            source, image, image_path, set()
        )
        cache_key = (pixel_path.resolve(), pixel_property or f"@{id(pixel_source)}")
        decoded = self.decoded.get(cache_key)
        if decoded is None:
            decoded = decode_source_canvas(pixel_source)
            self.decoded[cache_key] = decoded
        bitmap = decoded.copy()
        scale = min(1.0, MAX_CANVAS_EDGE / max(bitmap.width, bitmap.height))
        if scale < 1.0:
            size = (max(1, round(bitmap.width * scale)), max(1, round(bitmap.height * scale)))
            bitmap = bitmap.resize(size, Image.Resampling.LANCZOS)
            self.resized += 1
        output = WzCanvasProperty(source.name, parent)
        output.width, output.height = bitmap.size
        output.format, output.format2 = 1, 0
        output._png_data = encode_canvas_payload(
            bitmap, 1, bitmap.width, bitmap.height, key=GMS_KEY, listwz=False, zlib_level=6
        )
        output._png_length = len(output._png_data)
        output._png_offset = 0

        metadata: dict[str, object] = {}
        for candidate in (pixel_source, source):
            for child in candidate.children():
                if child.name not in {"_outlink", "_inlink"}:
                    metadata[child.name] = child
        for child in metadata.values():
            output.add(clone_property(child, output, image, image_path, self))
        if scale < 1.0:
            for node, _ in walk(output):
                if isinstance(node, WzVectorProperty):
                    node.x = round(int(node.x) * scale)
                    node.y = round(int(node.y) * scale)
        self.canvases += 1
        return output


def clone_property(source, parent, image: WzImage, image_path: Path, materializer: CanvasMaterializer, name=None):
    output_name = source.name if name is None else name
    if isinstance(source, WzCanvasProperty):
        old_name = source.name
        source.name = output_name
        try:
            return materializer.materialize(source, parent, image, image_path)
        finally:
            source.name = old_name
    if isinstance(source, WzSubProperty):
        output = WzSubProperty(output_name, parent)
        for child in source.children():
            output.add(clone_property(child, output, image, image_path, materializer))
        return output
    if isinstance(source, WzVectorProperty):
        return WzVectorProperty(output_name, int(source.x), int(source.y), parent)
    if isinstance(source, WzStringProperty):
        return WzStringProperty(output_name, str(source.value), parent)
    if isinstance(source, WzIntProperty):
        return WzIntProperty(output_name, int(source.value), parent)
    if isinstance(source, WzShortProperty):
        return WzShortProperty(output_name, int(source.value), parent)
    if isinstance(source, WzLongProperty):
        return WzLongProperty(output_name, int(source.value), parent)
    if isinstance(source, WzFloatProperty):
        return WzFloatProperty(output_name, float(source.value), parent)
    if isinstance(source, WzDoubleProperty):
        return WzDoubleProperty(output_name, float(source.value), parent)
    if isinstance(source, WzUolProperty):
        return WzUolProperty(output_name, str(source.value), parent)
    if isinstance(source, WzNullProperty):
        return WzNullProperty(output_name, parent)
    if isinstance(source, WzConvexProperty):
        output = WzConvexProperty(output_name, parent)
        output.points = [
            clone_property(point, output, image, image_path, materializer) for point in source.points
        ]
        return output
    if isinstance(source, WzSoundProperty):
        output = WzSoundProperty(output_name, parent)
        output.length_ms = source.length_ms
        output.header = source.header
        output._data_offset = source._data_offset
        output._data_length = source._data_length
        output._wz_image = source._wz_image
        output._data = source._data
        return output
    raise TypeError(f"unsupported WZ property: {type(source).__name__}")


def clone_image(source_path: Path, sanitizer=None) -> tuple[WzImage, CanvasMaterializer]:
    image = load_image(source_path, BMS_KEY)
    if sanitizer is not None:
        sanitizer(image.root)
    materializer = CanvasMaterializer()
    root = WzSubProperty(image.root.name)
    for child in image.root.children():
        root.add(clone_property(child, root, image, source_path, materializer))
    image._root = root
    image._parsed = True
    return image, materializer


def fill_legacy_mob_animation_gap(image: WzImage, mob_id: int) -> int:
    if mob_id != 8641002:
        return 0
    root = image.root
    attack = root.child("attack1")
    if not isinstance(attack, WzSubProperty):
        raise RuntimeError("8641002: missing attack1")
    attach = attack.get("info/hit/attach")
    if not isinstance(attach, WzIntProperty):
        raise RuntimeError("8641002: missing attack1/info/hit/attach")
    attach._value = 1
    names = [child.name for child in attack.children()]
    expected_without10 = [
        "info", *(str(index) for index in range(10)), *(str(index) for index in range(11, 16))
    ]
    if [name for name in names if name != "10"] != expected_without10:
        raise RuntimeError(f"8641002: unexpected attack1 order {names}")
    if "10" in names:
        if names != ["info", *(str(index) for index in range(16))]:
            raise RuntimeError(f"8641002: attack1/10 is not in sequence {names}")
        return 0
    frame9 = attack.child("9")
    if not isinstance(frame9, WzCanvasProperty) or frame9._png_data is None:
        raise RuntimeError("8641002: attack1/9 is not a materialized Canvas")
    frame10 = WzCanvasProperty("10", attack)
    frame10.width, frame10.height = int(frame9.width), int(frame9.height)
    frame10.format, frame10.format2 = int(frame9.format), int(frame9.format2)
    frame10._png_data = bytes(frame9._png_data)
    frame10._png_length = len(frame10._png_data)
    metadata_cloner = CanvasMaterializer()
    for child in frame9.children():
        frame10.add(clone_property(child, frame10, image, Path(), metadata_cloner))
    reordered = {}
    for name, child in attack._children.items():
        reordered[name] = child
        if name == "9":
            reordered["10"] = frame10
    attack._children = reordered
    return 1


def property_to_xml(prop, indent: int = 1) -> str:
    pad = "  " * indent
    name = f"name={quoteattr(prop.name)}"
    if isinstance(prop, WzNullProperty):
        return f"{pad}<null {name}/>"
    if isinstance(prop, WzVectorProperty):
        return f'{pad}<vector {name} x="{int(prop.x)}" y="{int(prop.y)}"/>'
    if isinstance(prop, WzCanvasProperty):
        attrs = f'{name} width="{int(prop.width)}" height="{int(prop.height)}" format="1"'
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<canvas {attrs}>{chr(10) + body + chr(10) + pad if body else ''}</canvas>"
    if isinstance(prop, WzSoundProperty):
        return f'{pad}<sound {name} length_ms="{int(prop.length_ms)}" bytes="{int(prop.value)}"/>'
    if isinstance(prop, WzConvexProperty):
        body = "\n".join(property_to_xml(point, indent + 1) for point in prop.points)
        return f"{pad}<extended {name}>\n{body}\n{pad}</extended>"
    if isinstance(prop, WzUolProperty):
        return f"{pad}<uol {name} value={quoteattr(str(prop.value))}/>"
    if isinstance(prop, WzSubProperty):
        body = "\n".join(property_to_xml(child, indent + 1) for child in prop.children())
        return f"{pad}<imgdir {name}>{chr(10) + body + chr(10) + pad if body else ''}</imgdir>"
    tags = {
        WzShortProperty: "short", WzIntProperty: "int", WzLongProperty: "long",
        WzFloatProperty: "float", WzDoubleProperty: "double", WzStringProperty: "string",
    }
    tag = next((value for kind, value in tags.items() if isinstance(prop, kind)), "string")
    return f"{pad}<{tag} {name} value={quoteattr(str(prop.value))}/>"


def image_to_xml(image: WzImage, name: str) -> str:
    body = "\n".join(property_to_xml(child) for child in image.root.children())
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<imgdir name="{name}">\n{body}\n</imgdir>\n'
    )


def town_for(map_id: int) -> int:
    return TOWN_BY_PREFIX[str(map_id)[:6]]


def sanitize_map(root: WzSubProperty, map_id: int) -> None:
    for child in list(root.children()):
        if child.name not in MAP_ROOTS:
            remove_child(root, child.name)
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in MAP_INFO_UNSUPPORTED:
            remove_child(info, name)
        if map_id in LEGACY_SWIM_MAPS:
            set_int(info, "swim", 1)
        if map_id in LEGACY_ZERO_FIELD_LIMIT_MAPS:
            set_int(info, "fieldLimit", 0)
        if map_id in MAP_ONLY_AB_TESTS or map_id in LEGACY_MEDIA_DISABLED_MAPS:
            remove_child(info, "bgm")
            remove_child(info, "mapMark")
        for name in ("returnMap", "forcedReturn"):
            value = child_value(info, name)
            allowed_maps = MAP_ID_SET | INSTALLED_ROUTE_MAP_IDS
            if isinstance(value, int) and value != 999999999 and value not in allowed_maps:
                set_int(info, name, town_for(map_id))

    life = root.child("life")
    if isinstance(life, WzSubProperty):
        if map_id in MAP_ONLY_AB_TESTS:
            life._children.clear()
        for entry in list(life.children()):
            if child_value(entry, "type") == "n":
                npc_id = int(child_value(entry, "id"))
                regional = str(npc_id).startswith("300")
                installed = (ROOT / f"clien/Data/Npc/{npc_id}.img").exists()
                hidden = int(child_value(entry, "hide") or 0) != 0
                if hidden or npc_id in REMOVED_NPCS or (not regional and not installed):
                    remove_child(life, entry.name)
                    continue
            for name in LIFE_UNSUPPORTED | LIFE_UNSUPPORTED_BY_MAP.get(map_id, set()):
                remove_child(entry, name)

    foothold = root.child("foothold")
    for node, _ in walk(foothold) if foothold is not None else ():
        if not isinstance(node, WzSubProperty):
            continue
        for name in FOOTHOLD_UNSUPPORTED_BY_MAP.get(map_id, set()):
            remove_child(node, name)

    for layer in [child for child in root.children() if child.name.isdigit()]:
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in list(objects.children()):
                values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
                modern_object = any(entry.child(name) is not None for name in ("questex", "tags", "timeScale"))
                if "2025MysticBloom" in values or entry.child("spineAni") is not None or modern_object:
                    remove_child(objects, entry.name)
                    continue
                if map_id != 450001000 and child_value(entry, "oS") == "extinction":
                    set_string(entry, "oS", "extinctionLegacy")
                for name in OBJ_UNSUPPORTED:
                    remove_child(entry, name)

    downgrade_connect_nodes(root)
    if map_id in LEGACY_CONNECT_FIRST_MAPS:
        normalize_connect_object_order(root)

    back = root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in list(back.children()):
            values = " ".join(str(getattr(child, "value", "")) for child in entry.children())
            if "2025MysticBloom" in values or int(child_value(entry, "ani") or 0) == 2:
                remove_child(back, entry.name)
                continue
            for name in BACK_UNSUPPORTED:
                remove_child(entry, name)

    portal = root.child("portal")
    if not isinstance(portal, WzSubProperty):
        return
    for portal_name, values in LEGACY_CHUCHU_SKY_WHALE_PORTALS.get(map_id, {}).items():
        record_name, portal_type, x, y, target_map, target_name = values
        entry = next(
            (
                node for node in portal.children()
                if child_value(node, "pn") == portal_name
            ),
            None,
        )
        if entry is None:
            entry = WzSubProperty(str(record_name), portal)
            portal.add(entry)
        set_string(entry, "pn", portal_name)
        set_int(entry, "pt", portal_type)
        set_int(entry, "x", x)
        set_int(entry, "y", y)
        set_int(entry, "tm", target_map)
        set_string(entry, "tn", target_name)
    downgrade_portal_types(root)
    for entry in list(portal.children()):
        portal_name = str(child_value(entry, "pn") or "")
        target = child_value(entry, "tm")
        script = str(child_value(entry, "script") or "")
        remove = False
        override = None
        cave_override = LEGACY_CAVE_ROUTE_PORTALS.get(map_id, {}).get(portal_name)
        cave_collision = LEGACY_CAVE_COLLISION_PORTALS.get(map_id, {}).get(portal_name)
        if cave_override is not None:
            set_int(entry, "pt", 2)
            set_int(entry, "tm", cave_override[0])
            set_string(entry, "tn", cave_override[1])
        elif cave_collision is not None:
            set_int(entry, "pt", 3)
            set_int(entry, "tm", cave_collision[0])
            set_string(entry, "tn", cave_collision[1])
        elif portal_name in PRESERVED_ARRIVAL_PORTALS.get(map_id, set()):
            set_int(entry, "pt", 0)
            set_int(entry, "tm", 999999999)
            set_string(entry, "tn", "")
        elif isinstance(target, int) and target != 999999999 and target not in (
            MAP_ID_SET | INSTALLED_ROUTE_MAP_IDS
        ):
            remove = True
        elif script and target == 999999999:
            remove = True
        if remove:
            remove_child(portal, entry.name)
            continue
        if override:
            set_int(entry, "tm", override[0])
            set_string(entry, "tn", override[1])
        remove_child(entry, "script")
        for name in PORTAL_UNSUPPORTED:
            remove_child(entry, name)


def project_legacy_mob_attack_info(root: WzSubProperty, mob_id: int) -> None:
    contract = LEGACY_BALLISTIC_ATTACKS.get(mob_id)
    if contract is None:
        return
    attack_number, bullet_speed = contract
    modern = root.get(f"info/attack/{attack_number - 1}")
    legacy = root.get(f"attack{attack_number}/info")
    if not isinstance(modern, WzSubProperty) or not isinstance(legacy, WzSubProperty):
        raise RuntimeError(f"{mob_id}: missing modern or legacy attack metadata")
    if child_value(modern, "action") != attack_number:
        raise RuntimeError(f"{mob_id}: modern ballistic attack action mismatch")
    if not isinstance(legacy.child("ball"), WzSubProperty):
        raise RuntimeError(f"{mob_id}: legacy ballistic attack has no ball node")
    expected = {"type": 2}
    if bullet_speed is not None:
        expected["bulletSpeed"] = bullet_speed
    for name, expected_value in expected.items():
        value = child_value(modern, name)
        if value != expected_value:
            raise RuntimeError(
                f"{mob_id}: unexpected info/attack/{attack_number - 1}/{name}={value}"
            )
        current = legacy.child(name)
        if current is None:
            legacy.add(WzIntProperty(name, expected_value, legacy))
        elif not isinstance(current, WzIntProperty) or int(current.value) != expected_value:
            raise RuntimeError(
                f"{mob_id}: conflicting attack{attack_number}/info/{name}"
            )

    if legacy.child("attackAfter") is None:
        raise RuntimeError(f"{mob_id}: ballistic attack has no attackAfter")
    ordered = {}
    canonical = ("range", "ball", "hit")
    for name in canonical:
        child = legacy.child(name)
        if child is not None:
            ordered[name] = child
    ordered["type"] = legacy._children["type"]
    attack_after = legacy.child("attackAfter")
    if attack_after is not None:
        ordered["attackAfter"] = attack_after
    if bullet_speed is not None:
        ordered["bulletSpeed"] = legacy._children["bulletSpeed"]
    for child in legacy.children():
        if child.name not in ordered and child.name not in expected:
            ordered[child.name] = child
    legacy._children = ordered


def sanitize_mob(root: WzSubProperty, mob_id: int) -> None:
    info = root.child("info")
    if not isinstance(info, WzSubProperty):
        raise RuntimeError(f"{root.name}: missing mob info")
    project_legacy_mob_attack_info(root, mob_id)
    for name in MOB_INFO_UNSUPPORTED:
        remove_child(info, name)
    for name, value in OLD_MOB_FIELDS.items():
        if info.child(name) is None:
            set_int(info, name, value)
    # Modern Arcane River EVA values (up to 930) make the legacy client miss
    # even at 999 accuracy. Keep the imported mobs on the old-client scale.
    set_int(info, "eva", 100)
    max_hp = info.child("maxHP")
    if max_hp is not None and int(max_hp.value) > 2_147_483_647:
        set_int(info, "maxHP", 2_147_483_647)


def sanitize_npc(root: WzSubProperty) -> None:
    info = root.child("info")
    if isinstance(info, WzSubProperty):
        for name in NPC_INFO_UNSUPPORTED:
            remove_child(info, name)
    # The old client supports condition actions only together with the matching
    # info/condition* selector.  Once that modern selector is removed, leaving
    # the root condition* trees creates dead UOL action graphs with a different
    # shape from the legacy NPC schema.
    for child in list(root.children()):
        suffix = child.name.removeprefix(NPC_ROOT_UNSUPPORTED_PREFIX)
        if child.name.startswith(NPC_ROOT_UNSUPPORTED_PREFIX) and suffix.isdigit():
            remove_child(root, child.name)


def collect_dependencies(image: WzImage) -> dict[str, object]:
    dependencies: dict[str, object] = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    bgm = child_value(image.root.child("info"), "bgm")
    mark = child_value(image.root.child("info"), "mapMark")
    if bgm:
        dependencies["bgms"].add(str(bgm))
    if mark:
        dependencies["marks"].add(str(mark))
    life = image.root.child("life")
    if isinstance(life, WzSubProperty):
        for entry in life.children():
            kind, value = child_value(entry, "type"), child_value(entry, "id")
            if kind == "m" and value is not None:
                dependencies["mobs"].add(int(value))
            elif kind == "n" and value is not None:
                dependencies["npcs"].add(int(value))
    back = image.root.child("back")
    if isinstance(back, WzSubProperty):
        for entry in back.children():
            resource, number = child_value(entry, "bS"), child_value(entry, "no")
            if resource and number is not None:
                branch = "ani" if int(child_value(entry, "ani") or 0) else "back"
                dependencies["assets"][("Back", str(resource))].add(f"{branch}/{number}")
    for layer in [child for child in image.root.children() if child.name.isdigit()]:
        tile_set = child_value(layer.child("info"), "tS")
        tiles = layer.child("tile")
        if tile_set and isinstance(tiles, WzSubProperty):
            for entry in tiles.children():
                unit, number = child_value(entry, "u"), child_value(entry, "no")
                if unit is not None and number is not None:
                    dependencies["assets"][("Tile", str(tile_set))].add(f"{unit}/{number}")
        objects = layer.child("obj")
        if isinstance(objects, WzSubProperty):
            for entry in objects.children():
                values = tuple(child_value(entry, key) for key in ("oS", "l0", "l1", "l2"))
                if all(value is not None for value in values):
                    dependencies["assets"][("Obj", str(values[0]))].add(
                        "/".join(str(value) for value in values[1:])
                    )
    return dependencies


def merge_dependency_sets(target: dict[str, object], source: dict[str, object]) -> None:
    for name in ("mobs", "npcs", "bgms", "marks"):
        target[name].update(source[name])
    for key, branches in source["assets"].items():
        target["assets"][key].update(branches)


def write_client_image(path: Path, image: WzImage) -> None:
    backup(path)
    atomic_write_bytes(path, encode_image_body(image, gms_reader()))


def write_server_image(path: Path, image: WzImage, name: str) -> None:
    backup(path)
    atomic_write_text(path, image_to_xml(image, name))


def verified_image_bytes(data: bytes, name: str) -> bytes:
    scan_img(data, region="GMS")
    image = WzImage.from_bytes(data, key=GMS_KEY, name=name)
    image.parse()
    if image.truncated or image.parse_warnings:
        raise RuntimeError(
            f"malformed generated {name}: truncated={image.truncated} "
            f"warnings={image.parse_warnings}"
        )
    return data


def raw_record_state(data: bytes) -> tuple[dict[tuple[str, ...], bytes], dict[tuple[str, ...], tuple[str, ...]]]:
    records: dict[tuple[str, ...], bytes] = {}
    orders: dict[tuple[str, ...], tuple[str, ...]] = {}

    def visit(prop_list, parent: tuple[str, ...] = ()) -> None:
        orders[parent] = tuple(record.name for record in prop_list.records)
        for record in prop_list.records:
            path = (*parent, record.name)
            records[path] = data[record.start:record.end]
            if record.children is not None:
                visit(record.children, path)

    visit(scan_img(data, region="GMS").root)
    return records, orders


def verify_raw_record_scope(
    before: bytes,
    after: bytes,
    approved_roots: set[tuple[str, ...]],
    *,
    allow_additions: bool,
) -> None:
    before_records, before_orders = raw_record_state(before)
    after_records, after_orders = raw_record_state(after)
    removed = set(before_records) - set(after_records)
    added = set(after_records) - set(before_records)
    if removed:
        raise RuntimeError(f"incremental IMG patch removed records: {sorted(removed)}")
    if not allow_additions and added:
        raise RuntimeError(f"scalar IMG patch added records: {sorted(added)}")
    if any(
        not any(path[:len(root)] == root for root in approved_roots)
        for path in added
    ):
        raise RuntimeError(f"incremental IMG patch added unapproved records: {sorted(added)}")
    for parent, names in before_orders.items():
        current = after_orders.get(parent)
        if current is None:
            raise RuntimeError(f"incremental IMG patch removed container: {parent}")
        expected = names if not allow_additions else current[:len(names)]
        if expected != names:
            raise RuntimeError(f"incremental IMG patch reordered siblings at {parent}")
    for path, raw in before_records.items():
        affected = any(
            path[:len(root)] == root or root[:len(path)] == path
            for root in approved_roots
        )
        if not affected and after_records[path] != raw:
            raise RuntimeError(f"incremental IMG patch changed protected record: {path}")


def verify_raw_record_insert_scope(
    before: bytes,
    after: bytes,
    approved_roots: set[tuple[str, ...]],
) -> None:
    """Verify additions inserted among siblings without changing legacy records."""
    before_records, before_orders = raw_record_state(before)
    after_records, after_orders = raw_record_state(after)
    removed = set(before_records) - set(after_records)
    added = set(after_records) - set(before_records)
    if removed:
        raise RuntimeError(f"incremental IMG insert removed records: {sorted(removed)}")
    if any(
        not any(path[:len(root)] == root for root in approved_roots)
        for path in added
    ):
        raise RuntimeError(f"incremental IMG insert added unapproved records: {sorted(added)}")

    for parent, names in before_orders.items():
        current = after_orders.get(parent)
        if current is None:
            raise RuntimeError(f"incremental IMG insert removed container: {parent}")
        added_children = {
            root[len(parent)]
            for root in approved_roots
            if len(root) == len(parent) + 1 and root[:len(parent)] == parent
            and root not in before_records
        }
        protected_order = tuple(name for name in current if name not in added_children)
        if protected_order != names:
            raise RuntimeError(f"incremental IMG insert reordered siblings at {parent}")

    for path, raw in before_records.items():
        affected = any(
            path[:len(root)] == root or root[:len(path)] == path
            for root in approved_roots
        )
        if not affected and after_records[path] != raw:
            raise RuntimeError(f"incremental IMG insert changed protected record: {path}")


def append_property_record(data: bytes, parent_path: tuple[str, ...], prop) -> bytes:
    """Append one complete property without reserializing any existing sibling."""
    layout = scan_img(data, region="GMS")
    prop_list, ancestors = _find_list(layout.root, parent_path)
    if any(record.name == prop.name for record in prop_list.records):
        raise FileExistsError("/".join((*parent_path, prop.name)))
    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    record = _record_bytes(prop, reader)
    count_edit = _count_edit(prop_list, prop_list.count + 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(record) + count_delta
    edits = [
        (prop_list.end, prop_list.end, record),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    result = verified_image_bytes(_apply_edits(data, edits), prop.name)
    verify_raw_record_scope(
        data, result, {(*parent_path, prop.name)}, allow_additions=True
    )
    return result


def insert_property_record_before(
    data: bytes,
    parent_path: tuple[str, ...],
    prop,
    before_name: str,
) -> bytes:
    """Insert one property before a sibling while preserving every old record."""
    layout = scan_img(data, region="GMS")
    prop_list, ancestors = _find_list(layout.root, parent_path)
    if any(record.name == prop.name for record in prop_list.records):
        raise FileExistsError("/".join((*parent_path, prop.name)))
    before = next(
        (record for record in prop_list.records if record.name == before_name),
        None,
    )
    if before is None:
        raise KeyError("/".join((*parent_path, before_name)))

    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    record = _record_bytes(prop, reader)
    count_edit = _count_edit(prop_list, prop_list.count + 1)
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(record) + count_delta
    edits = [
        (before.start, before.start, record),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    result = verified_image_bytes(_apply_edits(data, edits), prop.name)
    verify_raw_record_insert_scope(data, result, {(*parent_path, prop.name)})
    return result


def insert_property_records_before(
    data: bytes,
    parent_path: tuple[str, ...],
    props,
    before_name: str,
) -> bytes:
    """Insert multiple properties at one anchor without rewriting old siblings."""
    props = tuple(props)
    if not props:
        return data
    names = tuple(prop.name for prop in props)
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate inserted property names: {names}")

    layout = scan_img(data, region="GMS")
    prop_list, ancestors = _find_list(layout.root, parent_path)
    existing = {record.name for record in prop_list.records}
    conflicts = existing.intersection(names)
    if conflicts:
        raise FileExistsError("/".join((*parent_path, sorted(conflicts)[0])))
    before = next(
        (record for record in prop_list.records if record.name == before_name),
        None,
    )
    if before is None:
        raise KeyError("/".join((*parent_path, before_name)))

    reader = WzBinaryReader(io.BytesIO(data), GMS_KEY)
    records = b"".join(_record_bytes(prop, reader) for prop in props)
    count_edit = _count_edit(prop_list, prop_list.count + len(props))
    count_delta = len(count_edit[2]) - (count_edit[1] - count_edit[0])
    delta = len(records) + count_delta
    edits = [
        (before.start, before.start, records),
        count_edit,
        *_size_edits(ancestors, delta),
    ]
    edits.extend(_reference_edits(layout, edits))
    result = verified_image_bytes(_apply_edits(data, edits), before_name)
    approved = {(*parent_path, name) for name in names}
    verify_raw_record_insert_scope(data, result, approved)
    return result


def ensure_binary_parent(data: bytes, path: tuple[str, ...]) -> bytes:
    current: tuple[str, ...] = ()
    for part in path:
        image = WzImage.from_bytes(data, key=GMS_KEY)
        image.parse()
        if image.root.get("/".join((*current, part))) is None:
            data = append_property_record(data, current, WzSubProperty(part))
        current = (*current, part)
    return data


def append_xml_properties(text: str, parent_path: tuple[str, ...], props: list) -> str:
    root = scan_xml(text)
    current = root
    for part in parent_path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
        current = matches[0]
    existing = {child.name for child in current.children}
    duplicates = [prop.name for prop in props if prop.name in existing]
    if duplicates:
        raise FileExistsError(", ".join(duplicates))
    line_start = text.rfind("\n", 0, current.start) + 1
    indent = text[line_start:current.start]
    block = "".join(
        property_to_xml(prop, len(indent) // 2 + 1) + "\n" for prop in props
    )
    close_line_start = text.rfind("\n", 0, current.end_start) + 1
    insert_at = close_line_start if not text[close_line_start:current.end_start].strip() else current.end_start
    result = text[:insert_at] + block + text[insert_at:]
    scan_xml(result)
    return result


def insert_xml_properties_before(
    text: str,
    parent_path: tuple[str, ...],
    props: list,
    before_name: str,
) -> str:
    """Insert XML properties at one sibling anchor without rewriting old nodes."""
    root = scan_xml(text)
    current = root
    for part in parent_path:
        matches = [child for child in current.children if child.name == part]
        if len(matches) != 1:
            raise RuntimeError(f"XML path is not unique: {'/'.join(parent_path)}")
        current = matches[0]
    existing = {child.name for child in current.children}
    duplicates = [prop.name for prop in props if prop.name in existing]
    if duplicates:
        raise FileExistsError(", ".join(duplicates))
    anchors = [child for child in current.children if child.name == before_name]
    if len(anchors) != 1:
        raise RuntimeError(f"XML anchor is not unique: {before_name}")

    anchor = anchors[0]
    line_start = text.rfind("\n", 0, anchor.start) + 1
    indent = text[line_start:anchor.start]
    insert_at = line_start if not indent.strip() else anchor.start
    block = "".join(
        property_to_xml(prop, len(indent) // 2) + "\n" for prop in props
    )
    result = text[:insert_at] + block + text[insert_at:]
    scan_xml(result)
    return result


def migrate_maps() -> tuple[dict[str, object], dict[str, int]]:
    dependencies = {
        "assets": defaultdict(set), "mobs": set(), "npcs": set(), "bgms": set(), "marks": set()
    }
    totals = {"maps": 0, "canvases": 0, "links": 0, "resized": 0}
    for map_id in MAP_IDS:
        source = SOURCE / f"Map/Map/Map4/{map_id}.img"
        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        if client.exists():
            image = load_image(client, GMS_KEY)
            materializer = CanvasMaterializer()
        else:
            image, materializer = clone_image(
                source, lambda root, value=map_id: sanitize_map(root, value)
            )
            write_client_image(client, image)
        merge_dependency_sets(dependencies, collect_dependencies(image))
        for tree in ("wz", "wz-zh-CN"):
            map_root = ROOT / f"gms-server/{tree}/Map.wz"
            if not map_root.exists():
                continue
            server = map_root / f"Map/Map4/{map_id}.img.xml"
            if server.exists():
                ET.parse(server)
            else:
                write_server_image(server, image, f"{map_id}.img")
        if not source.exists():
            raise FileNotFoundError(source)
        totals["maps"] += 1
        totals["canvases"] += materializer.canvases
        totals["links"] += materializer.links
        totals["resized"] += materializer.resized
    return dependencies, totals


def ensure_path(root: WzSubProperty, path: str) -> WzSubProperty:
    current = root
    for name in [part for part in path.split("/") if part]:
        child = current.child(name)
        if not isinstance(child, WzSubProperty):
            remove_child(current, name)
            child = WzSubProperty(name, current)
            current.add(child)
        current = child
    return current


def normalize_legacy_asset_structure(image: WzImage, kind: str, name: str) -> int:
    changed = 0
    for (asset_kind, asset_name, path), renames in LEGACY_ASSET_CHILD_RENAMES.items():
        if (kind, name) != (asset_kind, asset_name):
            continue
        node = image.root.get(path)
        if not isinstance(node, WzSubProperty):
            raise RuntimeError(f"missing compatibility asset node: {kind}/{name}.img/{path}")
        for old_name, new_name in renames.items():
            old = node.child(old_name)
            new = node.child(new_name)
            if old is None and new is not None:
                continue
            if old is None or new is not None:
                raise RuntimeError(
                    f"unexpected compatibility asset children: {kind}/{name}.img/{path}"
                )
            node._children.pop(old_name)
            old.name = new_name
            node.add(old)
            changed += 1
    return changed


def legacy_asset_structure_errors(image: WzImage, kind: str, name: str) -> list[str]:
    errors = []
    for asset_kind, asset_name, path in LEGACY_ASSET_CHILD_RENAMES:
        if (kind, name) != (asset_kind, asset_name):
            continue
        node = image.root.get(path)
        names = [child.name for child in node.children()] if isinstance(node, WzSubProperty) else []
        expected = [str(index) for index in range(len(names))]
        if names != expected:
            errors.append(f"{kind}/{name}.img/{path}: {names}, expected {expected}")
    return errors


def merge_asset(kind: str, name: str, branches: set[str]) -> tuple[int, int, int]:
    source_path = SOURCE / f"Map/{kind}/{name}.img"
    target_path = ROOT / f"clien/Data/Map/{kind}/{name}.img"
    if kind == "Obj" and name == "connect":
        target = load_image(target_path, GMS_KEY) if target_path.exists() else None
        missing = [branch for branch in branches if target is None or target.root.get(branch) is None]
        if missing:
            raise FileNotFoundError(f"missing legacy Obj/connect.img branches: {missing}")
        return 0, 0, 0
    if not source_path.exists():
        target = load_image(target_path, GMS_KEY) if target_path.exists() else None
        missing = [branch for branch in branches if target is None or target.root.get(branch) is None]
        if missing:
            raise FileNotFoundError(f"missing {kind}/{name}.img branches: {missing}")
        return 0, 0, 0
    source = load_image(source_path, BMS_KEY)
    materializer = CanvasMaterializer()
    if target_path.exists():
        target_data = target_path.read_bytes()
        target = load_image(target_path, GMS_KEY)
    else:
        target = load_image(source_path, BMS_KEY)
        target._root = WzSubProperty(source.root.name)
        target._parsed = True
        target_data = None
    for branch in sorted(branches):
        source_node = source.root.get(branch)
        if source_node is None:
            if target.root.get(branch) is None:
                raise RuntimeError(f"source asset missing {kind}/{name}.img/{branch}")
            continue
        if target.root.get(branch) is not None:
            continue
        parent_path, _, leaf = branch.rpartition("/")
        parent_parts = tuple(part for part in parent_path.split("/") if part)
        cloned = clone_property(source_node, None, source, source_path, materializer, leaf)
        if target_data is None:
            parent = ensure_path(target.root, parent_path)
            parent.add(cloned)
        else:
            target_data = ensure_binary_parent(target_data, parent_parts)
            target_data = append_property_record(target_data, parent_parts, cloned)
            target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
            target.parse()
    normalize_legacy_asset_structure(target, kind, name)
    if target_data is None:
        write_client_image(target_path, target)
    elif target_data != target_path.read_bytes():
        backup(target_path)
        atomic_write_bytes(target_path, target_data)
    return materializer.canvases, materializer.links, materializer.resized


def migrate_map_assets(dependencies: dict[str, object]) -> dict[str, int]:
    totals = {"files": 0, "branches": 0, "canvases": 0, "links": 0, "resized": 0}
    jobs = [(kind, name, branches) for (kind, name), branches in sorted(dependencies["assets"].items())]
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = executor.map(merge_asset_job, jobs)
        for (_, _, branches), (canvases, links, resized) in zip(jobs, results, strict=True):
            totals["files"] += 1
            totals["branches"] += len(branches)
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def merge_asset_job(job: tuple[str, str, set[str]]) -> tuple[int, int, int]:
    kind, name, branches = job
    return merge_asset(kind, name, branches)


def merge_map_marks(marks: set[str]) -> int:
    source_path = SOURCE / "Map/MapHelper.img"
    target_path = ROOT / "clien/Data/Map/MapHelper.img"
    source = load_image(source_path, BMS_KEY)
    target = load_image(target_path, GMS_KEY)
    target_data = target_path.read_bytes()
    materializer = CanvasMaterializer()
    if target.root.child("mark") is None:
        target_data = ensure_binary_parent(target_data, ("mark",))
        target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
        target.parse()
    mark_root = target.root.child("mark")
    for mark in sorted(marks):
        if mark_root.child(mark) is not None:
            continue
        source_node = source.root.get(f"mark/{mark}")
        if source_node is None:
            raise RuntimeError(f"MapHelper missing mark/{mark}")
        cloned = clone_property(source_node, None, source, source_path, materializer, mark)
        target_data = append_property_record(target_data, ("mark",), cloned)
        target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
        target.parse()
        mark_root = target.root.child("mark")
    if target_data != target_path.read_bytes():
        backup(target_path)
        atomic_write_bytes(target_path, target_data)
    return materializer.canvases


def extract_mob(mob_id: int) -> Path:
    destination = MOB_CACHE / str(mob_id)
    output = destination / f"Mob_{mob_id:07d}.img"
    if output.exists():
        return output
    destination.mkdir(parents=True, exist_ok=True)
    errors = []
    for pack in sorted(PACKS.glob("Mob_*.ms")):
        result = subprocess.run(
            ["dotnet", str(MS_PROBE), str(pack), str(destination), f"Mob/{mob_id:07d}.img"],
            capture_output=True, text=True, check=False,
        )
        if output.exists():
            return output
        errors.append(f"{pack.name}: {result.stderr.strip() or result.stdout.strip()}")
    raise RuntimeError(f"unable to extract mob {mob_id}: {' | '.join(errors)}")


def migrate_one_mob(mob_id: int) -> tuple[int, int, int]:
    client = ROOT / f"clien/Data/Mob/{mob_id:07d}.img"
    server = ROOT / f"gms-server/wz/Mob.wz/{mob_id:07d}.img.xml"
    if client.exists():
        image = load_image(client, GMS_KEY)
        if child_value(image.root.child("info"), "eva") != 100:
            before = client.read_bytes()
            patched = mutate_img(
                before, "edit", ("info", "eva"),
                values={"value": 100}, region="GMS",
            ).data
            verify_raw_record_scope(
                before, patched, {("info", "eva")}, allow_additions=False
            )
            backup(client)
            atomic_write_bytes(client, patched)
            image = load_image(client, GMS_KEY)
        if not server.exists():
            write_server_image(server, image, f"{mob_id:07d}.img")
        else:
            text = server.read_text(encoding="utf-8")
            root = ET.fromstring(text)
            eva = root.find('./imgdir[@name="info"]/int[@name="eva"]')
            if eva is None:
                raise RuntimeError(f"existing server mob {mob_id} has no info/eva")
            if eva.get("value") != "100":
                text = mutate_xml(
                    text, "edit", ("info", "eva"), kind="Int", values={"value": 100}
                )
                backup(server)
                atomic_write_text(server, text)
        return 0, 0, 0
    source = extract_mob(mob_id)
    image, materializer = clone_image(source, lambda root: sanitize_mob(root, mob_id))
    fill_legacy_mob_animation_gap(image, mob_id)
    write_client_image(client, image)
    write_server_image(server, image, f"{mob_id:07d}.img")
    return materializer.canvases, materializer.links, materializer.resized


def migrate_mobs(mob_ids: set[int]) -> dict[str, int]:
    totals = {"mobs": 0, "canvases": 0, "links": 0, "resized": 0}
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(migrate_one_mob, sorted(mob_ids)):
            totals["mobs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def migrate_one_npc(npc_id: int) -> tuple[int, int, int]:
    client = ROOT / f"clien/Data/Npc/{npc_id:07d}.img"
    server = ROOT / f"gms-server/wz/Npc.wz/{npc_id:07d}.img.xml"
    if client.exists():
        image = load_image(client, GMS_KEY)
        if not server.exists():
            write_server_image(server, image, f"{npc_id:07d}.img")
        else:
            ET.parse(server)
        return 0, 0, 0
    source = SOURCE / f"Npc/{npc_id:07d}.img"
    image, materializer = clone_image(source, sanitize_npc)
    write_client_image(client, image)
    write_server_image(server, image, f"{npc_id:07d}.img")
    return materializer.canvases, materializer.links, materializer.resized


def migrate_npcs(npc_ids: set[int]) -> dict[str, int]:
    totals = {"npcs": 0, "canvases": 0, "links": 0, "resized": 0}
    regional = sorted(npc_id for npc_id in npc_ids if str(npc_id).startswith("300"))
    with ProcessPoolExecutor(max_workers=4) as executor:
        for canvases, links, resized in executor.map(migrate_one_npc, regional):
            totals["npcs"] += 1
            totals["canvases"] += canvases
            totals["links"] += links
            totals["resized"] += resized
    return totals


def transcode_legacy_mp3(source: WzSoundProperty) -> bytes:
    result = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "mp3", "-i", "pipe:0", "-map_metadata", "-1",
            "-codec:a", "libmp3lame", "-ar", "22050", "-ac", "2",
            "-b:a", "64k", "-write_xing", "0", "-id3v2_version", "0",
            "-write_id3v1", "0", "-f", "mp3", "pipe:1",
        ],
        input=_read_sound_payload(source), capture_output=True, check=False,
    )
    if result.returncode != 0 or not is_legacy_mp3_payload(result.stdout):
        raise RuntimeError(
            f"legacy MP3 transcode failed for {source.name}: "
            f"{result.stderr.decode('utf-8', 'replace').strip()}"
        )
    return result.stdout


def is_legacy_mp3_payload(payload: bytes) -> bool:
    """Return whether payload matches the imported 64 kbps legacy MP3 template."""
    if len(payload) < 4:
        return False
    header = int.from_bytes(payload[:4], "big")
    sync = (header >> 21) & 0x7FF
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    sample_rate_index = (header >> 10) & 0x3
    channel_mode = (header >> 6) & 0x3
    return (
        sync == 0x7FF
        and version == 0x2  # MPEG-2
        and layer == 0x1  # Layer III
        and bitrate_index == 0x8  # 64 kbps for MPEG-2 Layer III
        and sample_rate_index == 0x0  # 22.05 kHz for MPEG-2
        and channel_mode != 0x3  # stereo/joint stereo/dual channel, not mono
    )


def clone_sound(source: WzSoundProperty, parent, legacy_header: bytes) -> WzSoundProperty:
    payload = transcode_legacy_mp3(source)
    output = WzSoundProperty(source.name, parent)
    output.length_ms = source.length_ms
    output.header = legacy_header
    output._data_offset = 0
    output._data_length = len(payload)
    output._wz_image = None
    output._data = payload
    return output


def migrate_bgms(bgms: set[str]) -> dict[str, int]:
    legacy_image = load_image(ROOT / "clien/Data/Sound/Bgm12.img", GMS_KEY)
    legacy_sound = legacy_image.root.get("AquaCave")
    if not isinstance(legacy_sound, WzSoundProperty):
        raise RuntimeError("missing legacy Bgm12/AquaCave 64 kbps sound template")
    legacy_header = bytes(legacy_sound.header)
    by_pack: dict[str, set[str]] = defaultdict(set)
    for reference in bgms:
        pack, name = reference.split("/", 1)
        by_pack[pack].add(name)
    totals = {"packs": 0, "tracks": 0}
    for pack, names in sorted(by_pack.items()):
        source_path = SOURCE / f"Sound/{pack}.img"
        target_path = ROOT / f"clien/Data/Sound/{pack}.img"
        source = load_image(source_path, BMS_KEY)
        if target_path.exists():
            target = load_image(target_path, GMS_KEY)
            target_data = target_path.read_bytes()
        else:
            target = load_image(source_path, BMS_KEY)
            target._root = WzSubProperty(source.root.name)
            target._parsed = True
            target_data = None
        for name in sorted(names):
            if target.root.child(name) is not None:
                continue
            sound = source.root.get(name)
            if not isinstance(sound, WzSoundProperty):
                raise RuntimeError(f"missing sound {pack}/{name}")
            cloned = clone_sound(sound, None, legacy_header)
            if target_data is None:
                target.root.add(cloned)
            else:
                target_data = append_property_record(target_data, (), cloned)
                target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
                target.parse()
            totals["tracks"] += 1
        if target_data is None:
            write_client_image(target_path, target)
        elif target_data != target_path.read_bytes():
            backup(target_path)
            atomic_write_bytes(target_path, target_data)
        totals["packs"] += 1
    return totals


def source_map_string(image: WzImage, map_id: int):
    for category in image.root.children():
        node = category.child(str(map_id))
        if node is not None:
            return node
    return None


def upsert_client_strings(img_name: str, ids: set[int] | tuple[int, ...], category_name=None) -> int:
    source_path = SOURCE / f"String/{img_name}.img"
    target_path = ROOT / f"clien/Data/String/{img_name}.img"
    source = load_image(source_path, BMS_KEY)
    target = load_image(target_path, GMS_KEY)
    target_data = target_path.read_bytes()
    materializer = CanvasMaterializer()
    parent_path = (category_name,) if category_name else ()
    if category_name and target.root.child(category_name) is None:
        target_data = ensure_binary_parent(target_data, parent_path)
        target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
        target.parse()
    parent = target.root.get(category_name) if category_name else target.root
    changed = 0
    for item_id in sorted(ids):
        if parent.child(str(item_id)) is not None:
            continue
        node = source_map_string(source, item_id) if img_name == "Map" else source.root.get(str(item_id))
        if node is None:
            raise RuntimeError(f"String/{img_name}.img missing {item_id}")
        cloned = clone_property(node, None, source, source_path, materializer, str(item_id))
        target_data = append_property_record(target_data, parent_path, cloned)
        target = WzImage.from_bytes(target_data, key=GMS_KEY, name=target_path.name)
        target.parse()
        parent = target.root.get(category_name) if category_name else target.root
        changed += 1
    if target_data != target_path.read_bytes():
        backup(target_path)
        atomic_write_bytes(target_path, target_data)
    return changed


def upsert_server_strings(
    tree: str, img_name: str, ids: set[int] | tuple[int, ...], category_name=None
) -> int:
    source_path = SOURCE / f"String/{img_name}.img"
    source = load_image(source_path, BMS_KEY)
    target_path = ROOT / f"gms-server/{tree}/String.wz/{img_name}.img.xml"
    text = target_path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    parent = root if not category_name else next(
        (child for child in root if child.get("name") == category_name), None
    )
    if parent is None:
        raise RuntimeError(f"missing server string category: {category_name}")
    additions = []
    for item_id in sorted(ids):
        if any(child.get("name") == str(item_id) for child in parent):
            continue
        node = source_map_string(source, item_id) if img_name == "Map" else source.root.get(str(item_id))
        if node is None:
            raise RuntimeError(f"String/{img_name}.img missing {item_id}")
        additions.append(node)
    if additions:
        text = append_xml_properties(
            text, (category_name,) if category_name else (), additions
        )
        backup(target_path)
        atomic_write_text(target_path, text)
    return len(additions)


def migrate_strings(dependencies: dict[str, object]) -> dict[str, int]:
    regional_npcs = {value for value in dependencies["npcs"] if str(value).startswith("300")}
    totals = {
        "client_maps": upsert_client_strings("Map", MAP_IDS, "grandis"),
        "client_mobs": upsert_client_strings("Mob", dependencies["mobs"]),
        "client_npcs": upsert_client_strings("Npc", regional_npcs),
    }
    for tree in ("wz", "wz-zh-CN"):
        totals[f"{tree}_maps"] = upsert_server_strings(tree, "Map", MAP_IDS, "grandis")
        totals[f"{tree}_mobs"] = upsert_server_strings(tree, "Mob", dependencies["mobs"])
        totals[f"{tree}_npcs"] = upsert_server_strings(tree, "Npc", regional_npcs)
    return totals


def verify_preserved_files() -> None:
    if len(MAP_IDS) != 132 or MAP_ID_SET & BOSS_MAP_IDS:
        raise RuntimeError("non-boss expansion whitelist changed")
    for relative, expected in PRESERVED_FILE_SHA256.items():
        path = ROOT / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"preserved baseline changed: {relative} {actual}")
    for map_id in BOSS_MAP_IDS - {450009400, 450011990}:
        client = ROOT / f"clien/Data/Map/Map/Map4/{map_id}.img"
        if client.exists():
            raise RuntimeError(f"excluded boss map unexpectedly installed: {map_id}")


def verify_shared_file_states(*, require_final: bool) -> None:
    for relative, states in SHARED_FILE_STATES.items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        allowed = {states[-1]} if require_final else set(states)
        if actual not in allowed:
            raise RuntimeError(f"shared migration state is unknown: {relative} {actual}")


def main() -> int:
    if not SOURCE.exists() or not MS_PROBE.exists():
        raise SystemExit("TMS IMG source or MSProbe is missing")
    verify_preserved_files()
    verify_shared_file_states(require_final=False)
    print(f"Arcane River expansion maps: {len(MAP_IDS)}")
    print(f"Backups: {BACKUP_ROOT}")
    dependencies, map_stats = migrate_maps()
    print("maps", map_stats)
    print(
        "dependencies",
        {name: len(dependencies[name]) for name in ("assets", "mobs", "npcs", "bgms", "marks")},
    )
    print("map assets", migrate_map_assets(dependencies))
    print("map marks", merge_map_marks(dependencies["marks"]))
    print("npcs", migrate_npcs(dependencies["npcs"]))
    print("mobs", migrate_mobs(dependencies["mobs"]))
    print("bgms", migrate_bgms(dependencies["bgms"]))
    print("strings", migrate_strings(dependencies))
    verify_preserved_files()
    verify_shared_file_states(require_final=True)
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
