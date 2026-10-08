#!/usr/bin/env python3
"""Static contract checks for the multi-series nameplate DLL patch."""
import hashlib
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from set_panel_patch import LAYOUT_WINDOWS


PATH = sys.argv[1] if len(sys.argv) > 1 else "/Users/lizixian/Documents/mxd/BeiDou-Server/clien/BeiDouSetItemCompat.dll"
BASE_PATH = "/Users/lizixian/Documents/mxd/BeiDou-Server/tool/client-debug/BeiDouSetItemCompat/backup/BeiDouSetItemCompat.dll.before-title-series"
IMAGE_BASE = 0x65C80000
BASE_SHA256 = "10b660c8e6393df8219d2e134939a48b46770324be8e30056091d08fb783e4c8"


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + opt_size
    out = {}
    for i in range(count):
        off = table + i * 40
        name = data[off:off + 8].rstrip(b"\0").decode("ascii")
        vsize, va, raw_size, raw = struct.unpack_from("<IIII", data, off + 8)
        chars = struct.unpack_from("<I", data, off + 36)[0]
        out[name] = (vsize, va, raw_size, raw, chars)
    return out


data = open(PATH, "rb").read()
baseline = open(BASE_PATH, "rb").read()
assert hashlib.sha256(data).hexdigest() != BASE_SHA256, "DLL is still the unpatched baseline"
pe = struct.unpack_from("<I", data, 0x3C)[0]
checksum_off = pe + 24 + 64
stored_checksum = struct.unpack_from("<I", data, checksum_off)[0]
checksum_data = bytearray(data)
struct.pack_into("<I", checksum_data, checksum_off, 0)
checksum = 0
for i in range(0, len(checksum_data), 4):
    checksum += int.from_bytes(checksum_data[i:i + 4].ljust(4, b"\0"), "little")
    checksum = (checksum & 0xFFFFFFFF) + (checksum >> 32)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
assert stored_checksum == (checksum & 0xFFFF) + len(data)
changed = []
start = None
for i, (old, new) in enumerate(zip(baseline, data)):
    if old != new and start is None:
        start = i
    if old == new and start is not None:
        changed.append((start, i))
        start = None
if start is not None:
    changed.append((start, len(baseline)))
for start, end in changed:
    allowed = start < 0x400 or any(a <= start < b for a, b in (
        (0x1131, 0x1137), (0x1260, 0x1275), (0x1BDC, 0x1BE6), (0x1C1E, 0x1C4D),
        # stat-label patch: RVA 0x3673 (file 0x2A73) is the MesoRate tail of the
        # set-panel label chain, rewritten to `je +5 / jmp cave / nop` so the
        # PDD/MDD/ACC/EVA probes in .titles can run.  See patch_stat_labels.py
        # and test_stat_labels_contract.py for the exhaustive contract.
        (0x2A73, 0x2A7B),
        # .reloc rebuild: the baseline carries stale HIGHLOW entries pointing at
        # code padding. They are stripped so the image survives being loaded at a
        # relocated base (Wine/Box86), see fix_dll_reloc_hygiene.py.
        (0x4600, 0x4A00),
    ) + tuple((a - 0xc00, b - 0xc00) for a, b in LAYOUT_WINDOWS))
    assert allowed, (hex(start), hex(end))
sec = sections(data)
assert ".titles" in sec
assert sec[".data"][0] == sec[".data"][2] == 0x200
assert sec[".rdata"][0] == sec[".rdata"][2] == 0xA00
vsize, va, raw_size, raw, chars = sec[".titles"]
assert chars & 0x20000000 and chars & 0x80000000, hex(chars)
assert raw + vsize <= len(data) and raw_size >= vsize

text = sec[".text"]
text_bytes = data[text[3]:text[3] + text[0]]
assert text_bytes[0x1D31 - 0x1000:0x1D37 - 0x1000] == bytes.fromhex("807f08000f84")
assert text_bytes[0x281E - 0x1000:0x282D - 0x1000] == bytes.fromhex("0fb6bda4feffff85ff750431c931ff")
assert text_bytes[0x1E60 - 0x1000] == 0xE9

blob = data[raw:raw + vsize]
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True
insns = list(md.disasm(blob, IMAGE_BASE + va))
assert insns and insns[0].mnemonic == "call"
assert insns[1].mnemonic == "pop" and insns[2].mnemonic == "add"
# The image-base setup must add -(D2_RVA+5), because call/pop is absolute.
addend = struct.unpack_from("<I", blob, insns[2].address - (IMAGE_BASE + va) + 1)[0]
assert addend == (-(va + 5)) & 0xFFFFFFFF, hex(addend)
lookup = next(x for x in insns if x.address == IMAGE_BASE + va + 0x7D)
assert lookup.mnemonic == "movzx"
mem = lookup.operands[1].mem
assert lookup.reg_name(mem.base) == "eax"
assert lookup.reg_name(mem.index) == "edx"
assert mem.scale == 2
assert "三级神祇".encode("gbk") in blob
assert "缘壹之境".encode("gbk") in blob
assert "超觉醒者".encode("gbk") in blob

# --- tier ladder: the compare's operand ORDER is load-bearing -----------
# `39 /r` is CMP r/m32, r32, so it computes [threshold] - power. With a
# following `jb done` that means "stop as soon as the FIRST threshold is below
# the player's power" -> every account above 10k power was pinned to tier 0
# (the weakest title) while weak accounts got the strongest one.
# Only `3B /r` (CMP r32, r/m32) yields the intended "power < threshold -> stop".
ladder = next(x for x in insns if x.mnemonic == "cmp" and "ecx*4" in x.op_str)
assert ladder.bytes[0] == 0x3B, "ladder compare operands reversed: " + ladder.op_str
assert ladder.op_str.startswith("edx, dword ptr [eax + ecx*4"), ladder.op_str
assert insns[insns.index(ladder) + 1].mnemonic == "jb"

thr_rva = ladder.operands[1].mem.disp
thr = [struct.unpack_from("<I", data, raw + (thr_rva - va) + i * 4)[0] for i in range(8)]
assert thr == [10000, 100000, 1000000, 10000000,
               50000000, 200000000, 500000000, 2000000000], thr
snames = next(x for x in insns if x.address == IMAGE_BASE + va + 0x85)
assert snames.mnemonic == "lea"
name_rva = snames.operands[1].mem.disp
offs_rva = lookup.operands[1].mem.disp
name_base = raw + (name_rva - va)
offs_base = raw + (offs_rva - va)


def tier_for(power):
    lo, hi24 = power & 0xFFFFFFFF, (power >> 32) & 0xFFFFFF
    if hi24:
        if hi24 != 2:
            return 9 if hi24 > 2 else 8
        return 9 if lo >= 0x540BE400 else 8
    t = 0
    while t < 8 and lo >= thr[t]:
        t += 1
    return t


def title_for(series, power):
    idx = series * 10 + tier_for(power)
    o = struct.unpack_from("<H", data, offs_base + idx * 2)[0]
    return data[name_base + o:data.index(b"\0", name_base + o)].decode("gbk")


for power, want in ((0, "乾元玄阶"), (9999, "乾元玄阶"), (10000, "坤极天域"),
                    (999999, "天元墟境"), (1_000_000, "玄枢天宿"), (4_000_000, "玄枢天宿"),
                    (10_000_000, "星墟玄阙"), (100_000_000, "太白星河"),
                    (1_000_000_000, "昊天玄宿"), (2_000_000_000, "九曜神王"),
                    (10_000_000_000, "无敌大帝")):
    got = title_for(0, power)
    assert got == want, (power, got, want)
for series, want in ((1, "魂王"), (4, "中将"), (5, "破面十刃"), (8, "实习英雄")):
    got = title_for(series, 4_000_000)
    assert got == want, (series, got, want)
prev = -1
for power in list(range(0, 100000, 997)) + [10 ** k for k in range(5, 11)]:
    t = tier_for(power)
    assert t >= prev, (power, t, prev)
    prev = t

# --- relocation hygiene -------------------------------------------------
# Every base relocation must point at an address inside this image. Stale
# entries left over from earlier patches point at 0x90 code padding and turn
# into `mov [0x90909090], eax` once the loader applies a non-zero delta.
image_base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
size_of_image = struct.unpack_from("<I", data, pe + 24 + 56)[0]
dd = pe + 24 + 96
rel_rva, rel_size = struct.unpack_from("<II", data, dd + 5 * 8)
rel_sec = sec[".reloc"]
assert rel_rva == rel_sec[1] and rel_size == rel_sec[0], (hex(rel_rva), hex(rel_size))
rel_off = rel_sec[3]
off, entries, stale = rel_off, [], []
while off < rel_off + rel_size:
    page, block_size = struct.unpack_from("<II", data, off)
    assert block_size >= 8 and block_size % 4 == 0, (hex(page), block_size)
    assert off + block_size <= rel_off + rel_size, hex(page)
    for i in range((block_size - 8) // 2):
        word = struct.unpack_from("<H", data, off + 8 + i * 2)[0]
        if word >> 12:
            rva = page + (word & 0xFFF)
            target = None
            for name, (vsize, va, raw_size, raw, chars) in sec.items():
                if va <= rva < va + max(vsize, raw_size):
                    target = raw + (rva - va)
            assert target is not None, hex(rva)
            value = struct.unpack_from("<I", data, target)[0]
            entries.append(rva)
            if not (image_base <= value < image_base + size_of_image):
                stale.append((rva, value))
    off += block_size
assert len(entries) >= 300, len(entries)
assert not stale, [(hex(r), hex(v)) for r, v in stale]
for rva in (0x1D87, 0x1D9A, 0x1E64, 0x1EDC, 0x2849, 0x28CF, 0x28D8):
    assert rva not in entries, hex(rva)

print("nameplate series contract OK", PATH)
