#!/usr/bin/env python3
"""Add 9 title series to BeiDouSetItemCompat.dll on top of the int64 power patch.

Input baseline: backup/BeiDouSetItemCompat.dll.before-title-series
  (sha256 10b660c8e6393df8219d2e134939a48b46770324be8e30056091d08fb783e4c8)
Output: clien/BeiDouSetItemCompat.dll

Protocol (server sends state byte in the 0x17C enabled slot):
  0 = disabled, 1..9 = series 0..8 enabled.
Entry layout is unchanged:
  +0x00 charId, +0x04 power lo, +0x08 enabled|high24, +0x0C canvas.

Changes vs baseline:
  1. 0x1d31: cmp byte [edi+8],1 -> cmp byte [edi+8],0 (skip only when disabled).
  2. New PE section '.titles' (RWX) holding new D2 code + 9x10 title table.
  3. jmp at 0x1e60 retargeted to the new D2 (old D2 becomes dead bytes).
"""
import struct, shutil, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, 'backup', 'BeiDouSetItemCompat.dll.before-title-series')
BASE_SHA256 = '10b660c8e6393df8219d2e134939a48b46770324be8e30056091d08fb783e4c8'
DEFAULT_OUT = '/Users/lizixian/Documents/mxd/BeiDou-Server/clien/BeiDouSetItemCompat.dll'
OUT = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
IMG = 0x65c80000

import hashlib
if os.path.exists(OUT):
    with open(OUT, 'rb') as f:
        out_data = f.read()
    if b'.titles\x00' in out_data:
        print('already patched ->', OUT)
        sys.exit(0)
d = bytearray(open(BASE, 'rb').read())
assert hashlib.sha256(d).hexdigest() == BASE_SHA256, 'baseline sha256 mismatch'

TEXT_RVA, TEXT_RAW = 0x1000, 0x400
def ftext(rva): return TEXT_RAW + (rva - TEXT_RVA)

def expect(rva, blob):
    f = ftext(rva)
    assert bytes(d[f:f+len(blob)]) == blob, f'mismatch @{hex(rva)} {d[f:f+len(blob)].hex()}'

def patch(rva, blob):
    d[ftext(rva):ftext(rva)+len(blob)] = blob

def jmp32(src, dst):
    return b'\xe9' + struct.pack('<i', dst - (src + 5))

# ---------- sanity: baseline bytes ----------
expect(0x1d31, bytes.fromhex('807f08010f85'))

def expect_jmp_to_data(rva):
    f = ftext(rva)
    assert d[f] == 0xE9, f'not a jmp @{hex(rva)}'
    dst = IMG + rva + 5 + struct.unpack('<i', bytes(d[f+1:f+5]))[0]
    assert IMG + 0x4000 <= dst < IMG + 0x4200 or IMG + 0x3F00 <= dst < IMG + 0x4000, hex(dst)
    return dst

OLD_D2 = expect_jmp_to_data(0x1e60)
expect_jmp_to_data(0x27dc)
print(f'old D2 cave @{hex(OLD_D2)} (kept as dead bytes)')

# ---------- 1. enable check: skip only when state byte == 0 ----------
# Preserve the existing branch displacement, but invert JNE -> JE.
patch(0x1d31, b'\x80\x7f\x08\x00\x0f\x84')

# ---------- 2. title data ----------
SERIES = [
    ['乾元玄阶', '坤极天域', '天元墟境', '玄枢天宿', '星墟玄阙',
     '太白星河', '苍元帝宿', '昊天玄宿', '九曜神王', '无敌大帝'],
    ['魂师', '大魂师', '魂尊', '魂王', '魂圣',
     '封号斗罗', '极限斗罗', '三级神祇', '神帝'],
    ['赛亚人', '超级赛亚', '赛亚二阶', '赛亚三阶', '超赛神境',
     '超赛蓝境', '蓝级进化', '破坏神位', '自在极意'],
    ['学院生徒', '下忍', '中忍', '上忍', '影级强者',
     '仙人模式', '尾兽化身', '六道之力', '大筒木境'],
    ['海贼新秀', '超新星', '七武海', '中将', '四皇候补',
     '四皇', '大将', '觉醒者', '海贼王'],
    ['席官', '副队长', '队长', '破面十刃', '归刃解放',
     '完现术者', '零番队级', '灵王断片', '灵王'],
    ['鬼杀队员', '十人众级', '柱级', '下弦之鬼', '上弦之鬼',
     '上弦首座', '鬼舞辻无', '赫刀觉醒', '缘壹之境'],
    ['四级术师', '三级术师', '二级术师', '一级术师', '准特级位',
     '特别一级', '特级术师', '领域展开', '最强之境'],
    ['无个性者', '普通学生', '雄英生徒', '实习英雄', '职业英雄',
     '前十强者', '前五英雄', '第一英雄', '超觉醒者'],
]
THRESHOLDS = (10000, 100000, 1000000, 10000000,
              50000000, 200000000, 500000000, 2000000000)
assert len(SERIES) == 9 and all(len(s) == 9 for s in SERIES[1:])
assert len(SERIES[0]) == 10

rows = [SERIES[0]] + [s + [s[-1]] for s in SERIES[1:]]  # 9 rows x 10 cols
assert all(len(r) == 10 for r in rows)
names_blob, offs = b'', []
for row in rows:
    for t in row:
        offs.append(len(names_blob))
        names_blob += t.encode('gbk') + b'\x00'
assert len(names_blob) < 0x10000
offs_blob = struct.pack('<%dH' % len(offs), *offs)
thr_blob = struct.pack('<8I', *THRESHOLDS)
fmt = d.find(b'%s || ')
assert 0x3600 <= fmt < 0x4000, hex(fmt)
FMTD_RVA = 0x5000 + (fmt - 0x3600)

# ---------- 3. PE headers ----------
pe = struct.unpack('<I', bytes(d[0x3c:0x40]))[0]
nsec = struct.unpack('<H', bytes(d[pe+6:pe+8]))[0]
optsz = struct.unpack('<H', bytes(d[pe+20:pe+22]))[0]
sectab = pe + 24 + optsz
size_headers = struct.unpack('<I', bytes(d[pe+24+60:pe+24+64]))[0]
file_align = struct.unpack('<I', bytes(d[pe+24+36:pe+24+40]))[0]
size_image = struct.unpack('<I', bytes(d[pe+24+56:pe+24+60]))[0]
assert sectab + nsec * 40 + 40 <= size_headers, 'no room for new section header'

# The int64 base keeps executable compatibility caves in the .data raw tail.
# Its old VirtualSize (0x0c) excluded those addresses on strict loaders, which
# is the observed +0x400c execute fault. Map the already-present raw bytes.
data_header = None
for i in range(nsec):
    h = sectab + i * 40
    if bytes(d[h:h + 8]).rstrip(b'\0') == b'.data':
        data_header = h
        break
assert data_header is not None
data_vsize, data_va, data_raw_size, data_raw = struct.unpack_from('<IIII', d, data_header + 8)
assert data_va == 0x4000 and data_raw_size == 0x200 and data_vsize == 0x0c
struct.pack_into('<I', d, data_header + 8, data_raw_size)

rdata_header = None
for i in range(nsec):
    h = sectab + i * 40
    if bytes(d[h:h + 8]).rstrip(b'\0') == b'.rdata':
        rdata_header = h
        break
assert rdata_header is not None
rdata_vsize, rdata_va, rdata_raw_size, rdata_raw = struct.unpack_from('<IIII', d, rdata_header + 8)
assert rdata_va == 0x5000 and rdata_raw_size == 0xa00 and rdata_vsize == 0x908
struct.pack_into('<I', d, rdata_header + 8, rdata_raw_size)

NEW_VA = (size_image + 0xFFF) & ~0xFFF
NEW_RAW = (len(d) + file_align - 1) & ~(file_align - 1)

# ---------- 4. new D2 (series-aware), IMG-relative addressing ----------
code = bytearray()
code += b'\xe8\x00\x00\x00\x00\x58'              # call/pop; eax = absolute IMG+r+5
code += b'\x05' + struct.pack('<I', 0)           # placeholder add imm (fixed below)
ADD_POS = len(code) - 4
# (body appended after data layout is known)
body = bytearray()
body += b'\x89\x85\xb4\xfe\xff\xff'              # mov [ebp-0x14c],eax (IMG)
body += b'\x8b\x47\x04'                          # eax = lo
body += b'\x89\x85\xb0\xfe\xff\xff'              # mov [ebp-0x150],eax
body += b'\x8b\x57\x09\x81\xe2\xff\xff\xff\x00'  # edx = hi24
body += b'\x85\xd2\x75\x00'                      # test edx,edx; jnz hipath
HIP = len(body) - 1
body += b'\x31\xc9'                              # xor ecx,ecx
body += b'\x8b\x85\xb4\xfe\xff\xff'              # eax = IMG
body += b'\x8b\x95\xb0\xfe\xff\xff'              # edx = lo
LOOP = len(body)
# opcode 3B /r = CMP r32, r/m32  ->  cmp edx, [eax+ecx*4+THR2]  (dest = edx = power lo)
# NOTE: 39 /r is CMP r/m32, r32, i.e. the operands are REVERSED. With `jb done`
# that inverts the whole ladder: a power above the first threshold would exit
# immediately and every strong player would get tier 0 (the weakest title).
body += b'\x3b\x94\x88\x00\x00\x00\x00'          # cmp edx,[eax+ecx*4+THR2] (disp fixed below)
THR_POS = len(body) - 4
body += b'\x72\x06\x41\x83\xf9\x08\x72\xf1'      # jb done; inc; cmp 8; jb loop
DONE = len(body)
body += b'\xeb\x00'                              # jmp done2
HIPOS = len(body)
body[HIP] = (HIPOS - (HIP + 1)) & 0xFF
body += b'\x8b\x85\xb0\xfe\xff\xff'              # eax = lo
body += b'\xb9\x08\x00\x00\x00'                  # ecx = 8
body += b'\x83\xfa\x02\x77\x09\x72\x00'          # cmp edx,2; ja is10; jb done2
JB1 = len(body) - 1
body += b'\x3d\x00\xe4\x0b\x54\x72\x00'          # cmp eax,0x540BE400; jb done2
JB2 = len(body) - 1
body += b'\xb9\x09\x00\x00\x00'                  # ecx = 9
DONE2 = len(body)
body[DONE + 1] = (DONE2 - (DONE + 2)) & 0xFF
body[JB1] = (DONE2 - (JB1 + 1)) & 0xFF
body[JB2] = (DONE2 - (JB2 + 1)) & 0xFF
# series lookup: edx = state byte - 1, clamp 0..8
body += b'\x8b\x85\xb4\xfe\xff\xff'              # eax = IMG
body += b'\x0f\xb6\x57\x08'                      # movzx edx,byte[edi+8]
body += b'\x4a'                                  # dec edx
body += b'\x83\xfa\x08\x76\x00'                  # cmp edx,8; jbe sok
JBE = len(body) - 1
body += b'\x31\xd2'                              # xor edx,edx (fallback fantasy)
SOK = len(body)
body[JBE] = (SOK - (JBE + 1)) & 0xFF
body += b'\x8d\x14\x92'                          # lea edx,[edx+edx*4] (series*5)
body += b'\x03\xd2'                              # add edx,edx (series*10)
body += b'\x03\xd1'                              # add edx,ecx (+tier)
body += b'\x0f\xb7\x8c\x50\x00\x00\x00\x00'      # movzx ecx,word[eax+edx*2+SOFFS]
SOFFS_POS = len(body) - 4
body += b'\x8d\x90\x00\x00\x00\x00'              # lea edx,[eax+SNAMES]
SNAMES_POS = len(body) - 4
body += b'\x03\xd1'                              # add edx,ecx
body += b'\x89\x54\x24\x08'                      # mov [esp+8],edx (title)
body += b'\x8d\x8d\xe8\xfe\xff\xff'              # lea ecx,[ebp-0x118]
body += b'\x89\x4c\x24\x0c'                      # mov [esp+0xc],ecx
body += b'\x8d\x85\x08\xff\xff\xff'              # lea eax,[ebp-0xf8]
body += b'\x89\x04\x24'                          # mov [esp],eax
body += b'\x8b\x85\xb4\xfe\xff\xff'              # eax = IMG
body += b'\x8d\x88' + struct.pack('<I', FMTD_RVA)  # lea ecx,[eax+FMTD]
body += b'\x89\x4c\x24\x04'                      # mov [esp+4],ecx
body += b'\xe9\x00\x00\x00\x00'                  # jmp 0x1e75 (fixed below)
JMP_POS = len(body) - 4

# ---------- 5. section layout ----------
NEW_RVA = NEW_VA
D2_RVA = NEW_RVA
body_off = len(code)
THR2_RVA = NEW_RVA + body_off + len(body)
SNAMES_RVA = THR2_RVA + len(thr_blob)
SOFFS_RVA = SNAMES_RVA + len(names_blob)
# fixup code immediates (eax holds IMG, so lea [eax+RVA] uses disp32 = RVA)
# call/pop leaves the absolute address of D2_RVA+5 in EAX. Add the negative
# RVA; using IMG-RVA here would add the image base twice.
struct.pack_into('<I', code, ADD_POS, (-(D2_RVA + 5)) & 0xFFFFFFFF)
# NOTE: [eax+ecx*4+THR2] uses eax=IMG -> disp = THR2_RVA
struct.pack_into('<i', body, THR_POS, THR2_RVA)
struct.pack_into('<i', body, SOFFS_POS, SOFFS_RVA)
struct.pack_into('<i', body, SNAMES_POS, SNAMES_RVA)
# jmp rel = dst - (src+5); E9 sits at body[JMP_POS-1], all in RVA domain
rel = 0x1e75 - (D2_RVA + len(code) + JMP_POS - 1 + 5)
assert -0x80000000 <= rel < 0x80000000
full_code = bytes(code) + bytes(body[:JMP_POS]) + struct.pack('<i', rel)

# Cave_S + Cave_G relocated here: .text vsize ends exactly at 0x3FB4, so the
# old .text-slack caves are unmapped on strict loaders (execute fault i0=8).
S_RVA = NEW_RVA + len(full_code) + len(thr_blob) + len(names_blob) + len(offs_blob)
S = bytearray(
    b'\x8b\x8d\xc8\xfe\xff\xff'
    b'\x8b\x95\xcc\xfe\xff\xff'
    b'\x85\xd2'
    b'\x0f\x88' + struct.pack('<i', 0x27e6 - (S_RVA + 20)) +
    b'\xe9' + struct.pack('<i', 0x27f0 - (S_RVA + 25)))
assert len(S) == 25
G_RVA = S_RVA + len(S)
CB_RVA = 0x4031
G = bytearray(
    b'\x83\x7e\x0c\x00'
    b'\x75\x0d'
    b'\x85\xff'
    b'\x0f\x84' + struct.pack('<i', 0x2901 - (G_RVA + 14)) +
    b'\xe9' + struct.pack('<i', CB_RVA - (G_RVA + 19)) +
    b'\x89\xd0'
    b'\xc1\xe0\x08'
    b'\x09\xf8'
    b'\x39\x46\x08'
    b'\x75\x0a'
    b'\x39\x4e\x04'
    b'\x75\x05' +
    b'\xe9' + struct.pack('<i', 0x2901 - (G_RVA + 41)) +
    b'\xe9' + struct.pack('<i', CB_RVA - (G_RVA + 46)))
assert len(G) == 46
sec_data = full_code + thr_blob + names_blob + offs_blob + bytes(S) + bytes(G)
VSIZE = len(sec_data)
RAWSZ = (VSIZE + file_align - 1) & ~(file_align - 1)

# ---------- 6. write section ----------
d[sectab + nsec * 40:sectab + nsec * 40 + 40] = (
    b'.titles\x00' +
    struct.pack('<IIIIIIHHI', VSIZE, NEW_VA, RAWSZ, NEW_RAW, 0, 0, 0, 0, 0xE0000020))
d[pe+6:pe+8] = struct.pack('<H', nsec + 1)
d[pe+24+56:pe+24+60] = struct.pack('<I', NEW_VA + ((VSIZE + 0xFFF) & ~0xFFF))
d += b'\x00' * (NEW_RAW - len(d))
d[NEW_RAW:NEW_RAW + VSIZE] = sec_data
d += b'\x00' * (NEW_RAW + RAWSZ - len(d))

# ---------- 7. retarget draw-format jmp ----------
# Preserve the protocol's 1..9 series state instead of collapsing it to bool.
expect(0x281e, bytes.fromhex('bf010000000f954608750431c931ff'))
patch(0x281e, bytes.fromhex('0fb6bda4feffff85ff750431c931ff'))
f = TEXT_RAW + (0x1e60 - TEXT_RVA)
d[f:f+21] = b'\xe9' + struct.pack('<i', (IMG + D2_RVA) - (IMG + 0x1e60 + 5)) + b'\x90' * 16
f = TEXT_RAW + (0x27dc - TEXT_RVA)
d[f:f+10] = b'\xe9' + struct.pack('<i', (IMG + S_RVA) - (IMG + 0x27dc + 5)) + b'\x90' * 5
f = TEXT_RAW + (0x282d - TEXT_RVA)
d[f:f+32] = b'\xe9' + struct.pack('<i', (IMG + G_RVA) - (IMG + 0x282d + 5)) + b'\x90' * 27

# Recompute the PE checksum after changing the section table and file size.
checksum_off = pe + 24 + 64
struct.pack_into('<I', d, checksum_off, 0)
checksum = 0
for i in range(0, len(d), 4):
    word = int.from_bytes(d[i:i + 4].ljust(4, b'\0'), 'little')
    checksum += word
    checksum = (checksum & 0xffffffff) + (checksum >> 32)
checksum = (checksum & 0xffff) + (checksum >> 16)
checksum = (checksum & 0xffff) + (checksum >> 16)
struct.pack_into('<I', d, checksum_off, (checksum & 0xffff) + len(d))

open(OUT, 'wb').write(bytes(d))
print(f'new section .titles VA={hex(NEW_VA)} raw={hex(NEW_RAW)} vsize={hex(VSIZE)}')
print(f'new D2 @{hex(IMG + D2_RVA)} size={len(full_code)}; titles={len(names_blob)}B offs={len(offs_blob)}B')

# ---------- 8. relocation hygiene ----------
# The baseline carries HIGHLOW entries that point at 0x90 code padding left by
# earlier patches. They are harmless while the DLL loads at its preferred base
# (delta 0) but corrupt code once the loader relocates the image (Wine/Box86 on
# the phone): rva 0x1edc became `mov [0x90909090], eax` -> write AV, black screen.
import subprocess
subprocess.run([sys.executable, os.path.join(HERE, 'fix_dll_reloc_hygiene.py'),
                OUT, '--apply', '--quiet'], check=True)
print('WROTE', OUT)

# ---------- verify ----------
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
md = Cs(CS_ARCH_X86, CS_MODE_32)
insns = list(md.disasm(full_code, IMG + D2_RVA))
names = [x.mnemonic for x in insns]
assert names.count('call') == 1 and names.count('jmp') == 2, names
assert names.count('pop') == 1 and names[-1] == 'jmp', names
for x in insns:
    if x.mnemonic in ('jmp', 'jb', 'jbe', 'jnz', 'ja'):
        t = int(x.op_str, 16)
        ok = (D2_RVA + IMG <= t < D2_RVA + IMG + len(full_code)) or t == IMG + 0x1e75
        assert ok, (hex(x.address), x.mnemonic, x.op_str)

# Lock down the operand order of the ladder compare. `39 /r` (CMP r/m32, r32)
# computes [table] - power, so `jb done` fires as soon as the FIRST threshold is
# below the player's power -> everyone above 10k power is pinned to tier 0.
# Only `3B /r` (CMP r32, r/m32) means `power < threshold -> done`.
ladder = [x for x in insns if x.mnemonic == 'cmp' and 'ecx*4' in x.op_str]
assert len(ladder) == 1, [(x.mnemonic, x.op_str) for x in insns if x.mnemonic == 'cmp']
assert ladder[0].op_str.startswith('edx, dword ptr [eax + ecx*4'), \
    f'ladder compare operands reversed: {ladder[0].op_str}'
assert insns[insns.index(ladder[0]) + 1].mnemonic == 'jb'
# all data refs inside new section or known tables
blob = bytes(d)
assert blob[NEW_RAW:NEW_RAW+len(full_code)] == full_code
assert blob[NEW_RAW+len(full_code):NEW_RAW+len(full_code)+len(thr_blob)] == thr_blob
assert '三级神祇'.encode('gbk') in blob[NEW_RAW:]
assert '缘壹之境'.encode('gbk') in blob[NEW_RAW:]
assert '超觉醒者'.encode('gbk') in blob[NEW_RAW:]
# 0x1d31 one-byte change present
assert blob[ftext(0x1d31)+3] == 0x00
assert blob[ftext(0x1d31)+4:ftext(0x1d31)+6] == b'\x0f\x84'
print('series patch verify OK')
