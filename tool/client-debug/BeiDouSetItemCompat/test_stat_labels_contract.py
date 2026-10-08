#!/usr/bin/env python3
"""Static contract checks for the flat/percentage set-panel stat-label patch.

Run:  python3 test_stat_labels_contract.py [dll]
Default target: clien/BeiDouSetItemCompat.dll
Baseline:       backup/BeiDouSetItemCompat.dll.before-stat-labels
"""
import hashlib
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from set_panel_patch import (LAYOUT_WINDOWS, CAVE_RAW as LAYOUT_RAW, build_helpers,
                             STYLE_STRINGS_RAW, STYLE_TEXT)

HERE = "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/client-debug/BeiDouSetItemCompat"
PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/BeiDouSetItemCompat.dll"
BASE_PATH = HERE + "/backup/BeiDouSetItemCompat.dll.before-stat-labels"
BASE_SHA256 = "d6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0"

IMG = 0x65C80000
TEXT_RAW, TEXT_RVA = 0x400, 0x1000
TITLES_RAW, TITLES_RVA, TITLES_VSIZE_NEW = 0x4A00, 0x312000, 0x1000
RDATA_RAW, RDATA_RVA = 0x3600, 0x5000
RELOC_RAW, RELOC_RVA, RELOC_RAWSIZE = 0x4600, 0x311000, 0x400
WINDOW_RVA = 0x3673
CAVE_RAW = 0x4EAC
CAVE_RVA = TITLES_RVA + (CAVE_RAW - TITLES_RAW)
FALLBACK_LABEL = IMG + 0x548C
NEW_CHECKS = [("PDD", "物理防御力"), ("MDD", "魔法防御力"),
              ("ACC", "命中率"), ("EVA", "回避率"),
              ("STR", "力量"), ("DEX", "敏捷"), ("INT", "智力"), ("LUK", "运气"),
              ("STRPct", "力量"), ("DEXPct", "敏捷"), ("INTPct", "智力"), ("LUKPct", "运气"),
              ("PADPct", "攻击力"), ("MADPct", "魔法攻击力"),
              ("PDDPct", "物理防御力"), ("MDDPct", "魔法防御力"),
              ("ACCPct", "命中率"), ("EVAPct", "回避率"),
              ("HPPct", "最大HP"), ("MPPct", "最大MP"),
              ("SPD", "移动速度"), ("JMP", "跳跃力"), ("NormalDamage", "普通怪物伤害"),
              ("Damage", "伤害")]
BLOCK_LEN, KEY_IMM, LABEL_IMM = 28, 4, 18
CODE_LEN = len(NEW_CHECKS) * BLOCK_LEN + 10
COMMON_OFF = CODE_LEN - 5
# labels the chain resolved to before this patch (they must not move)
LEGACY = [("PAD", "攻击力"), ("MAD", "魔法攻击力"), ("HP", "最大HP"),
          ("MP", "最大MP"), ("FinalDamage", "最终伤害"), ("BossDamage", "Boss伤害"),
          ("ExpRate", "经验获得"), ("DropRate", "掉落率"), ("MesoRate", "金币获得")]


def ftext(rva):
    return TEXT_RAW + (rva - TEXT_RVA)


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    table = pe + 24 + struct.unpack_from("<H", data, pe + 20)[0]
    out, order = {}, []
    for i in range(count):
        off = table + i * 40
        name = data[off:off + 8].rstrip(b"\0").decode("ascii")
        vsize, va, raw_size, raw = struct.unpack_from("<IIII", data, off + 8)
        out[name] = (vsize, va, raw_size, raw)
        order.append(name)
    return out, pe, table, order


def reloc_entries(data, sec):
    vsize, va, raw_size, raw = sec[".reloc"]
    off, entries = raw, []
    while off < raw + vsize:
        page, bsize = struct.unpack_from("<II", data, off)
        assert bsize >= 8 and bsize % 4 == 0, (hex(page), bsize)
        for i in range((bsize - 8) // 2):
            word = struct.unpack_from("<H", data, off + 8 + i * 2)[0]
            if word >> 12:
                entries.append(page + (word & 0xFFF))
        off += bsize
    return entries


data = open(PATH, "rb").read()
baseline = open(BASE_PATH, "rb").read()
assert hashlib.sha256(baseline).hexdigest() == BASE_SHA256, "baseline is not the expected build"
assert data != baseline, "DLL is still the unpatched baseline"
sec, pe, table, order = sections(data)
assert len(baseline) == 0x5000
assert len(data) == 0x5A00

# ---- PE checksum -------------------------------------------------------
checksum_off = pe + 24 + 64
stored = struct.unpack_from("<I", data, checksum_off)[0]
buf = bytearray(data)
struct.pack_into("<I", buf, checksum_off, 0)
checksum = 0
for i in range(0, len(buf), 4):
    checksum += int.from_bytes(buf[i:i + 4].ljust(4, b"\0"), "little")
    checksum = (checksum & 0xFFFFFFFF) + (checksum >> 32)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
assert stored == (checksum & 0xFFFF) + len(data), hex(stored)

# ---- only the intended regions may differ ------------------------------
cave_end = CAVE_RAW + CODE_LEN + sum(len(key) + 1 for key, _ in NEW_CHECKS)
cave_end += cave_end % 2
cave_end += sum(len(label.encode('utf-16-le')) + 2 for _, label in NEW_CHECKS)
titles_h = table + order.index(".titles") * 40
reloc_h = table + order.index(".reloc") * 40
reloc_dir = pe + 24 + 96 + 5 * 8
allowed = [(ftext(WINDOW_RVA), ftext(WINDOW_RVA) + 8),      # the rewritten 8 bytes
           (CAVE_RAW, cave_end),                            # cave code + literals
           (titles_h + 8, titles_h + 12),                    # .titles VirtualSize
           (titles_h + 16, titles_h + 20),                  # .titles raw size
           (pe + 24 + 4, pe + 24 + 8),                      # SizeOfCode
           (reloc_h + 8, reloc_h + 12),                      # .reloc VirtualSize
           (reloc_dir + 4, reloc_dir + 8),                   # relocation dir size
           (RELOC_RAW, RELOC_RAW + RELOC_RAWSIZE),           # repacked by the tool
           (checksum_off, checksum_off + 4)] + [(ftext(a), ftext(b)) for a, b in LAYOUT_WINDOWS]
for i in range(len(baseline)):
    if baseline[i] != data[i]:
        assert any(a <= i < b for a, b in allowed), ("unexpected byte", hex(i))

# ---- .titles must now cover the cave ----------------------------------
t_vsize, t_va, t_rawsize, t_raw = sec[".titles"]
assert t_va == TITLES_RVA and t_raw == TITLES_RAW
assert t_vsize == TITLES_VSIZE_NEW and t_rawsize >= 0x600
assert t_va + t_vsize <= struct.unpack_from("<I", data, pe + 24 + 56)[0]
assert cave_end <= len(data), hex(cave_end)
layout_code, layout_symbols = build_helpers()
assert data[cave_end:LAYOUT_RAW] == b'\0' * (LAYOUT_RAW - cave_end)
assert data[LAYOUT_RAW:LAYOUT_RAW + len(layout_code)] == layout_code
assert data[LAYOUT_RAW + len(layout_code):STYLE_STRINGS_RAW] == b'\0' * (STYLE_STRINGS_RAW - LAYOUT_RAW - len(layout_code))
style_tail = bytearray(len(data) - STYLE_STRINGS_RAW)
for offset, text in STYLE_TEXT:
    encoded = text.encode('utf-16-le') + b'\0\0'
    style_tail[offset:offset + len(encoded)] = encoded
assert data[STYLE_STRINGS_RAW:] == style_tail
assert t_vsize >= (cave_end - TITLES_RAW), "cave outside the mapped VirtualSize"

# ---- window: je +5 / jmp cave / nop, no branch may enter it -----------
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True
w = list(md.disasm(data[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8], IMG + WINDOW_RVA))
assert [x.mnemonic for x in w] == ["je", "jmp", "nop"], [x.mnemonic for x in w]
assert int(w[0].op_str, 16) == IMG + 0x367A, w[0].op_str
assert int(w[1].op_str, 16) == IMG + CAVE_RVA, w[1].op_str
assert data[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 3] == b"\x74\x05\xe9"

text = sec[".text"]
tlo, thi = text[3], text[3] + text[0]
lo, hi = IMG + WINDOW_RVA, IMG + WINDOW_RVA + 8
for i in range(tlo, thi):
    va, op = IMG + text[1] + (i - tlo), data[i]
    cands = []
    if op in (0xE8, 0xE9):
        cands.append((5, struct.unpack_from("<i", data, i + 1)[0]))
    elif op == 0x0F and 0x80 <= data[i + 1] <= 0x8F:
        cands.append((6, struct.unpack_from("<i", data, i + 2)[0]))
    elif op == 0xEB or 0x70 <= op <= 0x7F:
        cands.append((2, struct.unpack_from("<b", data, i + 1)[0]))
    for length, rel in cands:
        # the patch's own `je +5` lands inside the window; nothing else may
        if va == IMG + WINDOW_RVA:
            assert va + length + rel == IMG + 0x367A and length == 2
            continue
        assert not (lo <= va + length + rel < hi), ("branch into the window", hex(va))

# ---- VA -> file offset map, then decode keys/labels -------------------
va_to_raw = {}
for name in order:
    vsize, va, raw_size, raw = sec[name]
    for rva in range(va, va + max(vsize, raw_size)):
        va_to_raw[IMG + rva] = raw + (rva - va)


def ansi(va):
    off = va_to_raw[va]
    end = data.index(b"\0", off)
    return data[off:end].decode("ascii")


def wide(va):
    off = va_to_raw[va]
    end = off
    while data[end:end + 2] != b"\0\0":
        end += 2
    return data[off:end].decode("utf-16-le")


# existing chain: nine `mov [esp+4], key` / `mov eax, label` pairs between the
# first block (RVA 0x3591) and the shared tail (RVA 0x367b).  The stride is not
# uniform -- the first four use `0f 84 rel32` (28 B) and the rest `74 rel8`
# (24 B) -- so pair them by pattern rather than by offset.
chain, pending = {}, None
end = va_to_raw[IMG + 0x367B]
for ins in md.disasm(data[va_to_raw[IMG + 0x3591]:end], IMG + 0x3591):
    if ins.mnemonic == "mov" and ins.op_str.startswith("dword ptr [esp + 4], "):
        pending = ins.operands[1].imm
    elif ins.mnemonic == "mov" and ins.op_str.startswith("eax, 0x") and pending is not None:
        chain[ansi(pending)] = wide(ins.operands[1].imm)
        pending = None
assert pending is None
for key, label in LEGACY:
    assert chain.get(key) == label, (key, chain.get(key), label)
assert len(chain) == 9, sorted(chain)

# ---- the cave ---------------------------------------------------------
cave = list(md.disasm(data[CAVE_RAW:CAVE_RAW + CODE_LEN], IMG + CAVE_RVA))
assert [x.mnemonic for x in cave][-1] == "jmp"
assert int(cave[-1].op_str, 16) == IMG + 0x367B, cave[-1].op_str
for ins in cave:
    assert ins.mnemonic not in ("pop", "enter", "leave", "sub", "add"), ins.mnemonic
assert sum(ins.mnemonic == "push" for ins in cave) == len(NEW_CHECKS) * 2

new_chain = {}
for i, (key, label) in enumerate(NEW_CHECKS):
    base = IMG + CAVE_RVA + i * BLOCK_LEN
    blk = list(md.disasm(data[CAVE_RAW + i * BLOCK_LEN:CAVE_RAW + (i + 1) * BLOCK_LEN], base))
    assert [x.mnemonic for x in blk] == ["mov", "mov", "call", "push", "push", "test", "mov", "je"], \
        [x.mnemonic for x in blk]
    assert blk[1].op_str == "dword ptr [esp], ebx"          # lstrcmpA arg1 = packet key
    assert blk[2].op_str == "esi"                            # lstrcmpA
    assert ansi(blk[0].operands[1].imm) == key, ansi(blk[0].operands[1].imm)
    assert [blk[3].op_str, blk[4].op_str] == ["edx", "edx"]
    assert wide(blk[6].operands[1].imm) == label, wide(blk[6].operands[1].imm)
    # the je targets the shared fallback inside the cave
    assert int(blk[7].op_str, 16) == IMG + CAVE_RVA + COMMON_OFF, blk[7].op_str
    new_chain[key] = wide(blk[6].operands[1].imm)

fallback_mov = list(md.disasm(data[CAVE_RAW + COMMON_OFF - 5:CAVE_RAW + COMMON_OFF], IMG + CAVE_RVA + COMMON_OFF - 5))
assert fallback_mov[0].mnemonic == "mov"
assert fallback_mov[0].operands[1].imm == FALLBACK_LABEL
assert wide(FALLBACK_LABEL) == "属性"

# ---- end-to-end label resolution -------------------------------------
full = dict(chain)
full.update(new_chain)


def label_for(key):
    return full.get(key, "属性")


def suffix_for(key):
    """Mirror of the probe at RVA 0x3507 / 0x3543 / 0x355c (case-sensitive)."""
    if any(t in key for t in ("Damage", "Rate", "Pct")):
        return "%"
    return "%" if key in ("StatusRes", "BuffDuration") else ""


def render(key, value):
    return "%s +%d%s" % (label_for(key), value, suffix_for(key))


for key, label in LEGACY:
    assert render(key, 5) == "%s +5%s" % (label, suffix_for(key)), key
for key, label in NEW_CHECKS:
    assert label_for(key) == label, (key, label_for(key))
    # PDD/MDD/ACC/EVA are flat values: no "%" suffix must be appended
    assert render(key, 30) == label + " +30" + suffix_for(key), render(key, 30)
    assert suffix_for(key) == ("%" if key.endswith(("Pct", "Damage")) else "")
# unknown keys still fall through to 属性
for key in ("", "PDDX", "pdd", "PD", "HPpct"):
    assert label_for(key) == "属性", (key, label_for(key))
    assert render(key, 1) == "属性 +1", render(key, 1)

# ---- relocation entries for the cave ---------------------------------
entries = reloc_entries(data, sec)
expect = []
for i in range(len(NEW_CHECKS)):
    expect.append(CAVE_RVA + i * BLOCK_LEN + KEY_IMM)
    expect.append(CAVE_RVA + i * BLOCK_LEN + LABEL_IMM)
expect.append(CAVE_RVA + COMMON_OFF - 4)          # fallback immediate
for rva in expect:
    assert rva in entries, ("cave immediate not relocated", hex(rva))
assert WINDOW_RVA + 1 not in entries, "the dead 0x3674 entry survived"
removed_layout = {0x307c, 0x30dc, 0x30e6, 0x322d,
                  0x2b92, 0x2d29, 0x312e, 0x31c1, 0x349f, 0x36c4}
assert not removed_layout.intersection(entries)
assert len(entries) == 323 - 1 + len(NEW_CHECKS) * 2 + 1 - len(removed_layout), len(entries)
assert len(entries) == len(reloc_entries(baseline, sections(baseline)[0])) - 1 + len(expect) - len(removed_layout)
rd = pe + 24 + 96 + 5 * 8
assert struct.unpack_from("<II", data, rd) == (RELOC_RVA, sec[".reloc"][0]), \
    struct.unpack_from("<II", data, rd)
size_of_image = struct.unpack_from("<I", data, pe + 24 + 56)[0]
for rva in entries:
    value = struct.unpack_from("<I", data, va_to_raw[IMG + rva])[0]
    assert value == 0 or IMG <= value < IMG + size_of_image, (hex(rva), hex(value))

# ---- simulate relocated loading: immediates move, branch encodings do not ----
delta = 0x12340000
rebased = bytearray(data)
for rva in entries:
    off = va_to_raw[IMG + rva]
    value = struct.unpack_from("<I", rebased, off)[0]
    struct.pack_into("<I", rebased, off, (value + delta) & 0xFFFFFFFF)
assert rebased[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8] == data[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8]
immediate_bytes = {rva + offset for rva in expect for offset in range(4)}
for offset in range(CODE_LEN):
    if CAVE_RVA + offset not in immediate_bytes:
        assert rebased[CAVE_RAW + offset] == data[CAVE_RAW + offset]
for index, (key, label) in enumerate(NEW_CHECKS):
    for slot, payload in ((KEY_IMM, key.encode('ascii') + b'\0'),
                          (LABEL_IMM, label.encode('utf-16-le') + b'\0\0')):
        off = CAVE_RAW + index * BLOCK_LEN + slot
        pointer = struct.unpack_from("<I", rebased, off)[0]
        target = va_to_raw[pointer - delta]
        assert rebased[target:target + len(payload)] == payload
    block = list(md.disasm(rebased[CAVE_RAW + index * BLOCK_LEN:CAVE_RAW + (index + 1) * BLOCK_LEN],
                           IMG + delta + CAVE_RVA + index * BLOCK_LEN))
    assert int(block[-1].op_str, 16) == IMG + delta + CAVE_RVA + COMMON_OFF

# Decoder capacities must agree with the backend/editor bounds.
assert data[ftext(0x2209):ftext(0x2209) + 3] == bytes.fromhex('83f860')  # cmp eax,96

# ---- legacy payloads must survive ------------------------------------
titles = data[TITLES_RAW:TITLES_RAW + t_vsize]
for blob in ("三级神祇", "缘壹之境", "超觉醒者", "乾元玄阶"):
    assert blob.encode("gbk") in titles, blob

print("stat labels contract OK", PATH)
