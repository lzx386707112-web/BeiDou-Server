#!/usr/bin/env python3
"""Build stat labels and complete set-panel layout from one immutable DLL baseline.

Input baseline: backup/BeiDouSetItemCompat.dll.before-stat-labels
  (sha256 d6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0,
   the shipped title-series build)
Output: clien/BeiDouSetItemCompat.dll

Why
---
The set-item panel turns each packet stat key into a Chinese label inside this
DLL.  The lookup is a straight-line chain of nine lstrcmpA checks against
hardcoded keys; anything that fails all nine falls back to the generic label
"属性" (VA 0x65c8548c). The extension adds eight missing flat labels and twelve
canonical percentage keys. Percentages reuse the existing case-sensitive Pct
suffix check; speed/jump and ordinary/normal-monster damage have separate labels.
Unknown keys still use the original fallback.

Chain addresses (image base 0x65c80000; .text RVA 0x1000 maps to file 0x400)
--------------------------------------------------------------------------
  RVA 0x3501  lea ebx,[eax+0x2b18]     ebx = packet key buffer (ANSI)
  RVA 0x3507  key contains "Damage" / "Rate" / "Pct"    -> suffix "%"
  RVA 0x3543  lstrcmpA(key,"StatusRes")
  RVA 0x355c  lstrcmpA(key,"BuffDuration")              -> suffix "%"
  RVA 0x356f  otherwise suffix = "" (VA 0x65c85414)
  RVA 0x357f  mov esi,[0x65f900f4]     esi = lstrcmpA (stdcall: callee pops args)
  RVA 0x3591  PAD          -> VA 0x65c8543a   each block is 28 bytes:
  RVA 0x35ad  MAD          -> VA 0x65c85442   8+3+2+2+1+5+1+6, where the two
  RVA 0x35c9  HP           -> VA 0x65c8544e   `push edx` slots reserve the
  RVA 0x35e5  MP           -> VA 0x65c85458   lstrcmpA argument area without a
  RVA 0x35fd  FinalDamage  -> VA 0x65c85462   `sub esp,8`
  RVA 0x3615  BossDamage   -> VA 0x65c8546c
  RVA 0x362d  ExpRate      -> VA 0x65c8547a
  RVA 0x3645  DropRate     -> VA 0x65c85484
  RVA 0x365d  MesoRate     -> VA 0x65c85492, else fallback VA 0x65c8548c
  RVA 0x3673  mov edx,fallback / cmovne eax,edx      <- replaced by this patch
  RVA 0x367b  shared tail: wsprintfW(buf, L"%s +%d%s", eax, value, suffix)
Labels are UTF-16LE because the format is wsprintfW (its %s takes wide strings);
keys are NUL-terminated ANSI because lstrcmpA is used.  Every absolute-VA
immediate in the chain carries a HIGHLOW relocation (RVA 0x3595, 0x35a2, ...,
0x3674), so the panel keeps working when the loader relocates the image (the
Wine/Box86 phone path).  This patch registers the same kind of entry for each
immediate it adds -- omitting them would render the labels as garbage there
at the preferred base. Windows also relocates DLLs, not only Wine/Box86.

Mechanics of this patch (purely additive)
-----------------------------------------
1. RVA 0x3673, the 8 bytes `ba 8c 54 c8 65 0f 45 c2` (mov edx,fallback; cmovne)
   become `74 05` / `e9 rel32` / `90`:
     key == MesoRate : je -> RVA 0x367a (nop) -> shared tail, eax = MesoRate label
     key != MesoRate : jmp to the cave
   The `push edx` slots at RVA 0x366c / 0x3672 are left untouched and the ZF
   from `test eax,eax` (RVA 0x366a) survives, because push and mov do not touch
   flags.  So at RVA 0x367b esp, eax, ebx, esi and the argument slots are exactly
   what the original code produced on either path.
2. A cave at file 0x4eac / VA 0x65f924ac (in the expanded .titles tail, RWX)
   runs twenty-four new lstrcmpA checks and jumps back to RVA 0x367b with
   eax = the label. Each stdcall pops eight argument bytes; two push edx
   instructions restore the scratch slots before testing the return value.
3. .titles VirtualSize and raw size grow to 0x1000 within the existing reserved
   image page. No RVA or SizeOfImage moves; the file grows 0x5000 -> 0x5a00.
4. .reloc gains one block (page 0x312000, 49 entries) for the cave immediates.
   The stale entry the baseline carried at RVA 0x3674 is consumed by the
   rewrite and is dropped by fix_dll_reloc_hygiene.py.
"""
import hashlib
import os
import struct
import sys
from fix_dll_reloc_hygiene import read_pe, parse_relocs as hygiene_relocs, rebuild_relocs

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'backup', 'BeiDouSetItemCompat.dll.before-stat-labels')
BASE_SHA256 = 'd6f9143373f50601f3020acc7277ec25c334de73c61b51f6a14a4a2529f839f0'
DEFAULT_OUT = '/Users/lizixian/Documents/mxd/BeiDou-Server/clien/BeiDouSetItemCompat.dll'
OUT = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT

IMG = 0x65C80000
TEXT_RVA, TEXT_RAW, TEXT_VSIZE = 0x1000, 0x400, 0x2FB4
# .titles stores its VirtualAddress as an RVA (0x312000), not as an absolute VA.
TITLES_RAW, TITLES_RVA = 0x4A00, 0x312000
TITLES_VA = IMG + TITLES_RVA                        # 0x65f92000
TITLES_VSIZE_OLD, TITLES_VSIZE_NEW, TITLES_RAWSIZE = 0x4AA, 0x1000, 0x1000
RELOC_RVA, RELOC_RAW, RELOC_VSIZE_OLD, RELOC_RAWSIZE = 0x311000, 0x4600, 0x2A4, 0x400

WINDOW_RVA = 0x3673
WINDOW_OLD = bytes.fromhex('ba8c54c8650f45c2')
WINDOW_NEW_HEAD = b'\x74\x05\xe9'
JE_TARGET_RVA = 0x367A
SHARED_TAIL_RVA = 0x367B
SHARED_TAIL = IMG + SHARED_TAIL_RVA                 # 0x65c8367b
CAVE_RAW = 0x4EAC
CAVE_RVA = TITLES_RVA + (CAVE_RAW - TITLES_RAW)     # 0x3124ac
CAVE_VA = IMG + CAVE_RVA                            # 0x65f924ac
FALLBACK_LABEL = IMG + 0x548C                       # "属性"
EXISTING_JE_SITES = (0x35A7, 0x35C3, 0x35DF, 0x35FB,
                     0x3613, 0x362B, 0x3643, 0x365B)
CHECKS = [('PDD', '物理防御力'), ('MDD', '魔法防御力'),
          ('ACC', '命中率'), ('EVA', '回避率'),
          ('STR', '力量'), ('DEX', '敏捷'), ('INT', '智力'), ('LUK', '运气'),
          ('STRPct', '力量'), ('DEXPct', '敏捷'), ('INTPct', '智力'), ('LUKPct', '运气'),
          ('PADPct', '攻击力'), ('MADPct', '魔法攻击力'),
          ('PDDPct', '物理防御力'), ('MDDPct', '魔法防御力'),
          ('ACCPct', '命中率'), ('EVAPct', '回避率'),
          ('HPPct', '最大HP'), ('MPPct', '最大MP'),
          ('SPD', '移动速度'), ('JMP', '跳跃力'), ('NormalDamage', '普通怪物伤害'),
          ('Damage', '伤害')]
BLOCK_LEN = 8 + 3 + 2 + 2 + 2 + 5 + 6                # stdcall cleanup + near JE
KEY_IMM, LABEL_IMM = 4, 18                           # offsets inside a block


def ftext(rva):
    return TEXT_RAW + (rva - TEXT_RVA)


def pe_of(data):
    return struct.unpack_from('<I', data, 0x3C)[0]


def parse_relocs(data, pe, header, rel_rva, rel_size):
    _, _, _, raw = struct.unpack_from('<IIII', data, header + 8)
    off, entries = raw, []
    while off < raw + rel_size:
        page, bsize = struct.unpack_from('<II', data, off)
        for i in range((bsize - 8) // 2):
            word = struct.unpack_from('<H', data, off + 8 + i * 2)[0]
            if word >> 12:
                entries.append(page + (word & 0xFFF))
        off += bsize
    return entries


d = bytearray(open(BASE, 'rb').read())
if hashlib.sha256(d).hexdigest() != BASE_SHA256:
    raise SystemExit('baseline sha256 mismatch')

# -------------------------------------------------------------- PE facts
pe = pe_of(d)
opt = pe + 24
nsec = struct.unpack_from('<H', d, pe + 6)[0]
optsz = struct.unpack_from('<H', d, pe + 20)[0]
sectab = opt + optsz
dd = opt + 96
image_base = struct.unpack_from('<I', d, opt + 28)[0]
size_of_image = struct.unpack_from('<I', d, opt + 56)[0]
assert image_base == IMG, hex(image_base)

headers = {}
for i in range(nsec):
    h = sectab + i * 40
    headers[bytes(d[h:h + 8]).rstrip(b'\0').decode('ascii')] = h
titles_h, reloc_h = headers['.titles'], headers['.reloc']
assert (struct.unpack_from('<IIII', d, titles_h + 8) ==
        (TITLES_VSIZE_OLD, TITLES_RVA, 0x600, TITLES_RAW))
assert (struct.unpack_from('<IIII', d, reloc_h + 8) ==
        (RELOC_VSIZE_OLD, RELOC_RVA, RELOC_RAWSIZE, RELOC_RAW))
assert (struct.unpack_from('<IIII', d, headers['.text'] + 8) ==
        (TEXT_VSIZE, TEXT_RVA, 0x3000, TEXT_RAW))
dir_rel_rva, dir_rel_size = struct.unpack_from('<II', d, dd + 5 * 8)
assert (dir_rel_rva, dir_rel_size) == (RELOC_RVA, RELOC_VSIZE_OLD)
checksum_off = opt + 64

# ------------------------------------------------------ baseline byte checks
assert bytes(d[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8]) == WINDOW_OLD, \
    'window mismatch: ' + bytes(d[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8]).hex()
assert bytes(d[ftext(SHARED_TAIL_RVA):ftext(SHARED_TAIL_RVA) + 6]) == \
    bytes.fromhex('8bb528fcffff'), 'shared tail mismatch'

# the nine existing `je` sites must still land on the shared tail ...
for rva in EXISTING_JE_SITES:
    f = ftext(rva)
    if d[f] == 0x0F and d[f + 1] == 0x84:
        tgt = IMG + rva + 6 + struct.unpack_from('<i', d, f + 2)[0]
    elif d[f] in (0x74, 0x75):
        tgt = IMG + rva + 2 + struct.unpack_from('<b', d, f + 1)[0]
    else:
        raise SystemExit('unexpected branch byte at %s: %02x' % (hex(rva), d[f]))
    assert tgt == SHARED_TAIL, (hex(rva), hex(tgt))

# ... and nothing anywhere in .text may branch into the 8 bytes we rewrite.
lo, hi = IMG + WINDOW_RVA, IMG + WINDOW_RVA + 8
intruders = []
for i in range(TEXT_RAW, TEXT_RAW + TEXT_VSIZE):
    va, op = IMG + TEXT_RVA + (i - TEXT_RAW), d[i]
    cands = []
    if op in (0xE8, 0xE9):
        cands.append((5, struct.unpack_from('<i', d, i + 1)[0]))
    elif op == 0x0F and 0x80 <= d[i + 1] <= 0x8F:
        cands.append((6, struct.unpack_from('<i', d, i + 2)[0]))
    elif op == 0xEB or 0x70 <= op <= 0x7F:
        cands.append((2, struct.unpack_from('<b', d, i + 1)[0]))
    for length, rel in cands:
        if lo <= va + length + rel < hi:
            intruders.append((hex(va), hex(va + length + rel)))
assert not intruders, 'patch window is a branch target: %s' % intruders

for token in (b'PDD', b'MDD\0', b'ACC\0', b'EVA\0'):
    assert token not in bytes(d), 'key already present: %r' % token
assert bytes(d[CAVE_RAW:0x5000]) == b'\0' * (0x5000 - CAVE_RAW), 'cave area not zero'

# the window currently owns a live relocation; it dies with the rewrite
old_relocs = parse_relocs(d, pe, reloc_h, RELOC_RVA, RELOC_VSIZE_OLD)
assert WINDOW_RVA + 1 in old_relocs, 'expected a HIGHLOW entry at RVA 0x3674'

# ------------------------------------------------------------- cave layout
assert len(d) == TITLES_RAW + 0x600
d.extend(b'\0' * (TITLES_RAWSIZE - 0x600))
code = bytearray()
je_rel32 = []
for _key, _label in CHECKS:
    code += b'\xc7\x44\x24\x04' + struct.pack('<I', 0)   # mov dword [esp+4], key
    code += b'\x89\x1c\x24'                              # mov [esp], ebx
    code += b'\xff\xd6'                                  # call esi   (lstrcmpA)
    code += b'\x52\x52'                                  # restore the two popped argument slots
    code += b'\x85\xc0'                                  # test eax, eax
    code += b'\xb8' + struct.pack('<I', 0)               # mov eax, label
    code += b'\x0f\x84' + b'\0' * 4                      # je common
    je_rel32.append(len(code) - 4)
assert len(code) == len(CHECKS) * BLOCK_LEN
code += b'\xb8' + struct.pack('<I', FALLBACK_LABEL)      # mov eax, "属性"
COMMON_OFF = len(code)
CODE_LEN = len(code) + 5                                 # + the trailing jmp

KEY_RAW = CAVE_RAW + CODE_LEN
KEY_VA = IMG + TITLES_RVA + (KEY_RAW - TITLES_RAW)
keys_blob, key_va = b'', {}
for key, _label in CHECKS:
    key_va[key] = KEY_VA + len(keys_blob)
    keys_blob += key.encode('ascii') + b'\0'
label_raw = KEY_RAW + len(keys_blob)
if label_raw % 2:
    keys_blob += b'\0'
    label_raw += 1
assert label_raw % 2 == 0, 'wide labels need 2-byte alignment'
LABEL_VA = IMG + TITLES_RVA + (label_raw - TITLES_RAW)
labels_blob, label_va = b'', {}
for _key, label in CHECKS:
    label_va[label] = LABEL_VA + len(labels_blob)
    labels_blob += label.encode('utf-16-le') + b'\0\0'
cave_end_raw = label_raw + len(labels_blob)
assert cave_end_raw <= TITLES_RAW + TITLES_RAWSIZE, hex(cave_end_raw)

reloc_targets = []
for index, (key, label) in enumerate(CHECKS):
    struct.pack_into('<I', code, index * BLOCK_LEN + KEY_IMM, key_va[key])
    struct.pack_into('<I', code, index * BLOCK_LEN + LABEL_IMM, label_va[label])
    reloc_targets.append(CAVE_RVA + index * BLOCK_LEN + KEY_IMM)
    reloc_targets.append(CAVE_RVA + index * BLOCK_LEN + LABEL_IMM)
reloc_targets.append(CAVE_RVA + COMMON_OFF - 4)          # the fallback immediate
                                                         # (COMMON_OFF-5 is the B8)
for pos in je_rel32:
    struct.pack_into('<i', code, pos, COMMON_OFF - (pos + 4))
code += b'\xe9' + struct.pack('<i', SHARED_TAIL - (CAVE_VA + len(code) + 5))
assert len(code) == CODE_LEN
reloc_targets.sort()
assert len(reloc_targets) == len(CHECKS) * 2 + 1 == len(set(reloc_targets))
assert all(CAVE_RVA <= t < CAVE_RVA + len(code) for t in reloc_targets)

# --------------------------------------------------------- write the patch
d[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8] = (
    b'\x74\x05' + b'\xe9' + struct.pack('<i', CAVE_VA - (IMG + WINDOW_RVA + 2 + 5)) + b'\x90')
d[CAVE_RAW:CAVE_RAW + len(code)] = bytes(code)
d[KEY_RAW:KEY_RAW + len(keys_blob)] = keys_blob
d[label_raw:label_raw + len(labels_blob)] = labels_blob
struct.pack_into('<I', d, titles_h + 8, TITLES_VSIZE_NEW)
struct.pack_into('<I', d, titles_h + 16, TITLES_RAWSIZE)
# The last section grows within the existing reserved image page; no RVA moves.
struct.pack_into('<I', d, opt + 4, struct.unpack_from('<I', d, opt + 4)[0] + TITLES_RAWSIZE - 0x600)
assert TITLES_RVA + TITLES_VSIZE_NEW <= size_of_image

# ---- one new .reloc block for page 0x312000 -------------------------------
page = CAVE_RVA & ~0xFFF
words = [0x3000 | (t & 0xFFF) for t in reloc_targets]
block = struct.pack('<II', page, 8 + len(words) * 2) + struct.pack('<%dH' % len(words), *words)
block += b'\0' * (-len(block) % 4)
block = block[:4] + struct.pack('<I', len(block)) + block[8:]
block_raw = RELOC_RAW + RELOC_VSIZE_OLD
assert block_raw % 4 == 0
assert bytes(d[block_raw:block_raw + len(block)]) == b'\0' * len(block), 'reloc tail not free'
assert RELOC_VSIZE_OLD + len(block) <= RELOC_RAWSIZE
d[block_raw:block_raw + len(block)] = block
reloc_vsize_new = RELOC_VSIZE_OLD + len(block)
struct.pack_into('<I', d, reloc_h + 8, reloc_vsize_new)
struct.pack_into('<I', d, dd + 5 * 8 + 4, reloc_vsize_new)

# Consume the superseded fallback relocation in memory before writing output.
info = read_pe(d)
blocks, _entries = hygiene_relocs(d, info)
relocations = rebuild_relocs(blocks, info, [WINDOW_RVA + 1], d)
d[RELOC_RAW:RELOC_RAW + RELOC_RAWSIZE] = relocations.ljust(RELOC_RAWSIZE, b'\0')
reloc_vsize_new = len(relocations)
struct.pack_into('<I', d, reloc_h + 8, reloc_vsize_new)
struct.pack_into('<I', d, dd + 5 * 8 + 4, reloc_vsize_new)

# Build the bounded-view rendering extension from the same immutable baseline.
from set_panel_patch import apply_layout, CAVE_RAW as LAYOUT_RAW, STYLE_STRINGS_RAW, RETAINED_RELOCS
layout_windows, layout_size, layout_symbols = apply_layout(d, ftext)
info = read_pe(d)
blocks, layout_entries = hygiene_relocs(d, info)
layout_removed = [entry['rva'] for entry in layout_entries
                  if entry['rva'] not in RETAINED_RELOCS
                  and any(start <= entry['rva'] < end for start, end in layout_windows)]
relocations = rebuild_relocs(blocks, info, layout_removed, d)
d[RELOC_RAW:RELOC_RAW + RELOC_RAWSIZE] = relocations.ljust(RELOC_RAWSIZE, b'\0')
reloc_vsize_new = len(relocations)
struct.pack_into('<I', d, reloc_h + 8, reloc_vsize_new)
struct.pack_into('<I', d, dd + 5 * 8 + 4, reloc_vsize_new)

struct.pack_into('<I', d, checksum_off, 0)
checksum = 0
for i in range(0, len(d), 4):
    checksum += int.from_bytes(d[i:i + 4].ljust(4, b'\0'), 'little')
    checksum = (checksum & 0xFFFFFFFF) + (checksum >> 32)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
checksum = (checksum & 0xFFFF) + (checksum >> 16)
struct.pack_into('<I', d, checksum_off, (checksum & 0xFFFF) + len(d))
already_patched = os.path.exists(OUT) and open(OUT, 'rb').read() == bytes(d)

# ------------------------------------------------------------- verification
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

blob = bytes(d)
md = Cs(CS_ARCH_X86, CS_MODE_32)
pe2 = pe_of(blob)
sectab2 = pe2 + 24 + struct.unpack_from('<H', blob, pe2 + 20)[0]
h2 = {}
for i in range(struct.unpack_from('<H', blob, pe2 + 6)[0]):
    h = sectab2 + i * 40
    h2[bytes(blob[h:h + 8]).rstrip(b'\0').decode('ascii')] = h

# -- the rewritten window: je +5 / jmp cave / nop --------------------------
w = list(md.disasm(blob[ftext(WINDOW_RVA):ftext(WINDOW_RVA) + 8], IMG + WINDOW_RVA))
assert [x.mnemonic for x in w] == ['je', 'jmp', 'nop'], [x.mnemonic for x in w]
assert int(w[0].op_str, 16) == IMG + JE_TARGET_RVA, w[0].op_str
assert int(w[1].op_str, 16) == CAVE_VA, w[1].op_str
assert blob[ftext(WINDOW_RVA) + 7] == 0x90

# -- the cave: extended lstrcmpA(key, literal) probes, then the fallback ---
for index, (key, label) in enumerate(CHECKS):
    base = index * BLOCK_LEN
    blk = list(md.disasm(bytes(code[base:base + BLOCK_LEN]), CAVE_VA + base))
    assert [x.mnemonic for x in blk] == ['mov', 'mov', 'call', 'push', 'push', 'test', 'mov', 'je'], \
        [x.mnemonic for x in blk]
    assert blk[0].op_str == 'dword ptr [esp + 4], %#x' % key_va[key], blk[0].op_str
    assert blk[1].op_str == 'dword ptr [esp], ebx', blk[1].op_str
    assert blk[2].op_str == 'esi', blk[2].op_str
    assert [blk[3].op_str, blk[4].op_str] == ['edx', 'edx']
    assert blk[5].op_str == 'eax, eax', blk[5].op_str
    assert blk[6].op_str == 'eax, %#x' % label_va[label], blk[6].op_str
    assert int(blk[7].op_str, 16) == CAVE_VA + COMMON_OFF, blk[7].op_str
tail = list(md.disasm(bytes(code[COMMON_OFF - 5:]), CAVE_VA + COMMON_OFF - 5))
assert [x.mnemonic for x in tail] == ['mov', 'jmp'], [x.mnemonic for x in tail]
assert tail[0].op_str == 'eax, %#x' % FALLBACK_LABEL, tail[0].op_str
assert int(tail[1].op_str, 16) == SHARED_TAIL, tail[1].op_str
# Every stdcall has the same balanced scratch-slot discipline as the legacy chain.
assert sum(ins.mnemonic == 'push' for ins in md.disasm(bytes(code), CAVE_VA)) == len(CHECKS) * 2
for ins in md.disasm(bytes(code), CAVE_VA):
    assert ins.mnemonic not in ('pop', 'enter', 'leave', 'add', 'sub'), ins.mnemonic

# -- literals landed where the immediates point ---------------------------
for index, (key, label) in enumerate(CHECKS):
    for off, want in ((KEY_IMM, key.encode('ascii') + b'\0'),
                      (LABEL_IMM, label.encode('utf-16-le') + b'\0\0')):
        imm = struct.unpack_from('<I', code, index * BLOCK_LEN + off)[0]
        at = TITLES_RAW + (imm - TITLES_VA)
        assert blob[at:at + len(want)] == want, (key, label, hex(imm))

# -- the existing chain must be bit-identical around the change -----------
for rva, old in ((0x3501, '8d98182b0000'), (0x357f, '8b35f400f965'),
                 (0x365D, 'c74424040956c865'), (0x366C, '52'),
                 (0x3672, '52'), (0x367B, '8bb528fcffff')):
    got = bytes(blob[ftext(rva):ftext(rva) + len(old) // 2]).hex()
    assert got == old, (hex(rva), got)

# -- relocations: all cave immediates are registered, the dead one is gone
new_relocs = parse_relocs(blob, pe2, h2['.reloc'],
                          *struct.unpack_from('<II', blob, pe2 + 24 + 96 + 5 * 8))
for t in reloc_targets:
    assert t in new_relocs, hex(t)
assert WINDOW_RVA + 1 not in new_relocs, 'stale entry at RVA 0x3674 survived'
assert struct.unpack_from('<I', blob, h2['.reloc'] + 8)[0] == reloc_vsize_new
assert struct.unpack_from('<I', blob, pe2 + 24 + 96 + 5 * 8 + 4)[0] == reloc_vsize_new
assert len(new_relocs) == len(old_relocs) - 1 + len(reloc_targets) - len(layout_removed)
# every entry must still point at a dword that lives inside this image
rva_to_raw = {}
for name, hh in h2.items():
    vs, va, rs, raw = struct.unpack_from('<IIII', blob, hh + 8)
    for rva in range(va, va + max(vs, rs)):
        rva_to_raw[rva] = raw + (rva - va)
for rva in new_relocs:
    value = struct.unpack_from('<I', blob, rva_to_raw[rva])[0]
    assert value == 0 or IMG <= value < IMG + size_of_image, (hex(rva), hex(value))

# -- nothing outside the intended windows may differ ---------------------
baseline = open(BASE, 'rb').read()
assert len(blob) == TITLES_RAW + TITLES_RAWSIZE
assert len(baseline) == 0x5000
allowed = (
    (ftext(WINDOW_RVA), ftext(WINDOW_RVA) + 8),        # the 8 rewritten bytes
    (CAVE_RAW, cave_end_raw),                          # cave code + literals
    (titles_h + 8, titles_h + 12),                     # .titles VirtualSize
    (titles_h + 16, titles_h + 20),                    # .titles SizeOfRawData
    (opt + 4, opt + 8),                               # SizeOfCode
    (reloc_h + 8, reloc_h + 12),                       # .reloc VirtualSize
    (dd + 5 * 8 + 4, dd + 5 * 8 + 8),                  # relocation directory size
    (checksum_off, checksum_off + 4),                  # PE checksum
    # The whole .reloc area: fix_dll_reloc_hygiene.py repacks the block chain
    # when it drops the stale 0x3674 entry, so byte-level comparison there is
    # meaningless.  The reloc checks above are the real gate.
    (RELOC_RAW, RELOC_RAW + RELOC_RAWSIZE),
) + tuple((ftext(a), ftext(b)) for a, b in layout_windows) + (
    (LAYOUT_RAW, LAYOUT_RAW + layout_size), (STYLE_STRINGS_RAW, STYLE_STRINGS_RAW + 0x40))
outside = [(hex(i), baseline[i], blob[i]) for i in range(len(baseline))
           if baseline[i] != blob[i] and not any(a <= i < b for a, b in allowed)]
assert not outside, 'unexpected bytes changed: %s' % outside[:8]
assert struct.unpack_from('<H', blob, pe2 + 6)[0] == nsec
assert struct.unpack_from('<I', blob, h2['.titles'] + 8)[0] == TITLES_VSIZE_NEW

sec = blob[TITLES_RAW:TITLES_RAW + TITLES_VSIZE_NEW]
for _key, label in CHECKS:
    assert label.encode('utf-16-le') in sec, label
assert '三级神祇'.encode('gbk') in sec, 'title series data lost'

print('window RVA %#x: je->%#x / jmp->%#x / nop' % (WINDOW_RVA, IMG + JE_TARGET_RVA, CAVE_VA))
print('cave VA=%#x raw=%#x code=%d keys=%d labels=%d end=%#x'
      % (CAVE_VA, CAVE_RAW, len(code), len(keys_blob), len(labels_blob), cave_end_raw))
print('.titles VirtualSize %#x -> %#x ; .reloc %#x -> %#x (%d -> %d entries)'
      % (TITLES_VSIZE_OLD, TITLES_VSIZE_NEW, RELOC_VSIZE_OLD, reloc_vsize_new,
         len(old_relocs), len(new_relocs)))
print('WROTE', OUT)
if already_patched:
    print('already patched (whole-file identical) ->', OUT)
else:
    with open(OUT, 'wb') as output:
        output.write(blob)
print('sha256', hashlib.sha256(blob).hexdigest())
