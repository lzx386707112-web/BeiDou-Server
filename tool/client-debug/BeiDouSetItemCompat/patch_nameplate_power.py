#!/usr/bin/env python3
"""Patch BeiDouSetItemCompat.dll for int64 power, tier prefix, and stable refresh.
Writes patched DLL in place (backs up original once). Verifies by re-disassembly.
"""
import hashlib, struct, shutil, os, sys

DEFAULT_SRC = '/Users/lizixian/Documents/mxd/BeiDou-Server/clien/BeiDouSetItemCompat.dll'
SRC = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
BAK = SRC + '.bak.int32'
BASE_SHA256 = '66350f6eae8120d65873a6f08febb144a5c21babb7671b6d9a769c3f4969265b'
PATCHED_SHA256 = '10b660c8e6393df8219d2e134939a48b46770324be8e30056091d08fb783e4c8'
IMG = 0x65c80000
TEXT_RVA, TEXT_RAW = 0x1000, 0x400
DATA_RVA, DATA_RAW = 0x4000, 0x3400
RDATA_RVA, RDATA_RAW = 0x5000, 0x3600

current = open(SRC, 'rb').read()
current_sha256 = hashlib.sha256(current).hexdigest()
if not os.path.exists(BAK) and current_sha256 == PATCHED_SHA256:
    print('already patched ->', SRC)
    sys.exit(0)
if not os.path.exists(BAK):
    assert current_sha256 == BASE_SHA256, f'unexpected input sha256: {current_sha256}'
    shutil.copy2(SRC, BAK)
    print('backup ->', BAK)
d = bytearray(open(BAK, 'rb').read())
assert hashlib.sha256(d).hexdigest() == BASE_SHA256, 'baseline backup sha256 mismatch'

def ftext(rva): return TEXT_RAW + (rva - TEXT_RVA)
def fdata(rva): return DATA_RAW + (rva - DATA_RVA)
def frdata(rva): return RDATA_RAW + (rva - RDATA_RVA)
SEG = {'text': ftext, 'data': fdata, 'rdata': frdata}

def expect(rva, blob, seg='text'):
    f = SEG[seg](rva)
    assert bytes(d[f:f+len(blob)]) == blob, f'mismatch @{hex(rva)} {d[f:f+len(blob)].hex()}'

def patch(rva, blob, seg='text'):
    d[SEG[seg](rva):SEG[seg](rva)+len(blob)] = blob

def jmp32(src, dst):
    return b'\xe9' + struct.pack('<i', dst - (src + 5))

def jmp_site(rva, dst, size):
    patch(rva, jmp32(rva, dst) + b'\x90' * (size - 5))

# ---------- sanity ----------
expect(0x2783, bytes.fromhex('8d4b0b'))
expect(0x27bc, bytes.fromhex('b904000000'))
expect(0x27dc, bytes.fromhex('8b8dc8feffff85c9790a'))
expect(0x27f0, bytes.fromhex('ba0100000089d8898da0feffffe8aeeaffff8b8da0feffff'))
expect(0x2823, bytes.fromhex('0f954608'))
expect(0x1d31, bytes.fromhex('807f0801'))
expect(0x1f34, bytes.fromhex('8d8508ffffff'))
assert set(d[0x400+0x2fb4:0x400+0x3000]) == {0}, 'text slack dirty'
assert set(d[0x340c:0x3600]) == {0}, 'data slack dirty'
assert set(d[0x3600+0x908:0x3600+0xa00]) == {0}, 'rdata slack dirty'

# ---------- inline 1-byte patches ----------
patch(0x2783, b'\x8d\x4b\x0f')                 # pkt len 11 -> 15
patch(0x27bc, b'\xb9\x08\x00\x00\x00')         # power memcpy 4 -> 8
patch(0x2823, b'\x0f\x95\x46\x08')             # enabled stays [esi+8]; canvas keeps [esi+12]
patch(0x1d31, b'\x80\x7f\x08\x01')             # enabled stays [edi+8]; canvas keeps [edi+12]

# ---------- allocators ----------
dcap, rcap = DATA_RVA + 0x00c, RDATA_RVA + 0x908
def put_code(b):
    global dcap
    r = dcap; dcap += len(b)
    assert dcap <= DATA_RVA + 0x200, 'data slack overflow'
    patch(r, b, 'data'); return r
def put_data(b):
    global rcap
    r = rcap; rcap += len(b)
    assert rcap <= RDATA_RVA + 0xa00, 'rdata slack overflow'
    patch(r, b, 'rdata'); return r

def pc_add(rva):
    # emits: call $+5 (5B) ; pop eax (1B) ; add eax,imm32 (5B) = 11B; eax = IMG
    pc = rva + 5  # RVA of value popped = address just after call
    # runtime: eax = IMG + pc ; want IMG -> imm = -pc
    return b'\xe8\x00\x00\x00\x00\x58\x05' + struct.pack('<I', (-pc) & 0xffffffff), pc

# ---------- rdata: tiers / tables / strings ----------
TIERS = ['乾元玄阶', '坤极天域', '天元墟境', '玄枢天宿', '星墟玄阙',
         '太白星河', '苍元帝宿', '昊天玄宿', '九曜神王', '无敌大帝']
THRESHOLDS = (10000, 100000, 1000000, 10000000,
              50000000, 200000000, 500000000, 2000000000, 10000000000)

def tier_for_power(power):
    tier = 0
    while tier < len(THRESHOLDS) and power >= THRESHOLDS[tier]:
        tier += 1
    return TIERS[tier]

assert tier_for_power(0) == '乾元玄阶'
assert tier_for_power(9999) == '乾元玄阶'
assert tier_for_power(10000) == '坤极天域'
assert tier_for_power(9999999999) == '九曜神王'
assert tier_for_power(10000000000) == '无敌大帝'

nb, offs = b'', []
for t in TIERS:
    offs.append(len(nb)); nb += t.encode('gbk') + b'\x00'
NAMES = put_data(nb)
OFFS = put_data(bytes(offs))
THR = put_data(struct.pack('<8I', *THRESHOLDS[:8]))
FMTB = put_data(b'A %d %d %08X %08X\x00')
FMTC = put_data(b'O %d %d %08X %08X\x00')
FMTE = put_data(b'D %d %08X %08X\x00')
FMTD = put_data(b'%s || ' + '战斗力：%s'.encode('gbk') + b'\x00')

# ---------- Cave_S: sign check (text slack) ----------
CS = 0x3fb4
jmp_site(0x27dc, CS, 10)
patch(CS, b'\x8b\x8d\xc8\xfe\xff\xff'
          b'\x8b\x95\xcc\xfe\xff\xff'
          b'\x85\xd2'
          b'\x0f\x88' + struct.pack('<i', 0x27e6 - (CS + 20)) +
          jmp32(CS + 20, 0x27f0))

# ---------- Cave_G: skip unchanged or already-inactive nameplates ----------
# Packet handling used to refresh every tracked player for every 0x17C packet.
# The refresh releases all nameplate canvases before recreating the enabled
# ones. Avoid that lifecycle churn when this entry has no visible state change.
CG = CS + 25
guard = bytearray(
    b'\x83\x7e\x0c\x00'                          # cmp dword [esi+12],0
    b'\x75\x0d'                                  # jne has_canvas
    b'\x85\xff'                                  # test edi,edi
    b'\x0f\x84' + struct.pack('<i', 0x2901 - (CG + 14)))
guard += jmp32(CG + 14, 0x4031)                  # enabled but canvas missing
guard += (
    b'\x89\xd0'                                  # has_canvas: mov eax,edx
    b'\xc1\xe0\x08'                              # shl eax,8
    b'\x09\xf8'                                  # or eax,edi
    b'\x39\x46\x08'                              # cmp [esi+8],eax
    b'\x75\x0a'                                  # jne update
    b'\x39\x4e\x04'                              # cmp [esi+4],ecx
    b'\x75\x05')                                 # jne update
guard += jmp32(CG + 36, 0x2901)                  # identical visible state
guard += jmp32(CG + 41, 0x4031)                  # update
assert len(guard) == 46
patch(CG, guard)

# ---------- Cave_A: alloc + reload lo/hi ----------
def build_A(r):
    return (b'\xba\x01\x00\x00\x00\x89\xd8\x89\x8d\xa0\xfe\xff\xff'
            b'\xe8' + struct.pack('<i', 0x12b0 - (r + 13 + 5)) +
            b'\x8b\x8d\xa0\xfe\xff\xff\x8b\x95\xcc\xfe\xff\xff\x8b\xf0'
            + jmp32(r + 32, 0x280a))
CA = put_code(build_A(dcap))
assert dcap - CA == 37
jmp_site(0x27f0, CA, 24)

# ---------- Cave_B: entry store + accept log ----------
def build_B(r):
    o = bytearray(b'\x89\x4e\x04'              # power low
                  b'\x89\xd0\xc1\xe0\x08'    # high 24 -> bytes 9..11
                  b'\x09\xf8\x89\x46\x08'    # enabled -> byte 8; store packed
                  b'\x89\x95\xd0\xfe\xff\xff')
    base, pc = pc_add(r + len(o)); o += base
    o += b'\x89\x4c\x24\x10'
    o += b'\x8d\x88' + struct.pack('<I', FMTB)
    o += (b'\x89\x4c\x24\x04\x89\x5c\x24\x08\x89\x7c\x24\x0c'
          b'\x8d\x95\xe8\xfe\xff\xff\x89\x14\x24'
          b'\x8b\x95\xd0\xfe\xff\xff\x89\x54\x24\x14'
          b'\xff\x90\x14\x01\x31\x00')
    o += jmp32(r + len(o), 0x2853)
    return bytes(o)
CB = put_code(build_B(dcap))
jmp_site(0x282d, CG, 32)

# ---------- Cave_C: OK log with hi ----------
def build_C(r):
    o = bytearray(b'\x8b\x46\x04\x8b\x56\x09\x81\xe2\xff\xff\xff\x00\x89\x95\xd0\xfe\xff\xff'
                  b'\x89\x44\x24\x10')
    base, pc = pc_add(r + len(o)); o += base
    o += b'\x8d\x88' + struct.pack('<I', FMTC)
    o += (b'\x89\x4c\x24\x04\x89\x5c\x24\x08'
          b'\x8d\x9d\xe8\xfe\xff\xff\x89\x1c\x24'
          b'\x89\x7c\x24\x0c'
          b'\x8b\x95\xd0\xfe\xff\xff\x89\x54\x24\x14'
          b'\xff\x90\x14\x01\x31\x00')
    # We already emitted the success log. Jump past the original formatter and
    # logger; 0x28dc expects EBX to point at its stack buffer, but EBX is charId.
    o += jmp32(r + len(o), 0x2901)
    return bytes(o)
CC = put_code(build_C(dcap))
jmp_site(0x28b6, CC, 38)

# ---------- Cave_D1: u64 -> dec string without wsprintfA ----------
def build_D1(r):
    o = bytearray(
        b'\x8b\xb3\x80\x00\x00\x00'              # mov esi,[ebx+0x80]
        b'\x57\x53'                                # push edi; push ebx
        b'\x8b\x47\x04'                            # mov eax,[edi+4] (low)
        b'\x8b\x5f\x08'                            # mov ebx,[edi+8] (enabled + high 24)
        b'\xc1\xeb\x08'                            # shr ebx,8
        b'\x8d\xbd\x5f\xff\xff\xff'              # lea edi,[ebp-0xa1]
        b'\xc6\x07\x00')                          # mov byte [edi],0
    divide = len(o)
    o += (b'\x31\xd2'                              # xor edx,edx
          b'\xb9\x0a\x00\x00\x00'                # mov ecx,10
          b'\x93'                                  # xchg eax,ebx
          b'\xf7\xf1'                              # div ecx (high word)
          b'\x93'                                  # xchg eax,ebx
          b'\xf7\xf1'                              # div ecx (low word)
          b'\x4f'                                  # dec edi
          b'\x80\xc2\x30'                          # add dl,'0'
          b'\x88\x17'                              # mov [edi],dl
          b'\x89\xc2'                              # mov edx,eax
          b'\x09\xda'                              # or edx,ebx
          b'\x75\x00')                             # jnz divide
    o[-1] = (divide - len(o)) & 0xff
    o += b'\x8d\x95\x48\xff\xff\xff'            # lea edx,[ebp-0xb8]
    copy = len(o)
    o += (b'\x8a\x0f'                              # mov cl,[edi]
          b'\x88\x0a'                              # mov [edx],cl
          b'\x47\x42'                              # inc edi; inc edx
          b'\x84\xc9'                              # test cl,cl
          b'\x75\x00')                             # jnz copy
    o[-1] = (copy - len(o)) & 0xff
    o += b'\x5b\x5f'                              # pop ebx; pop edi
    o += jmp32(r + len(o), 0x1d9e)
    assert len(o) <= 75
    return bytes(o)
CD1 = put_code(build_D1(dcap))
jmp_site(0x1d7a, CD1, 36)

# ---------- Cave_D2: tier select + final format ----------
def build_D2(r):
    o = bytearray(b'\xe8\x00\x00\x00\x00\x58')   # call/pop; pc1 follows
    pc1 = r + 5                                    # call pushes the next instruction
    o += b'\x89\x85\xb4\xfe\xff\xff'             # mov [ebp-0x14c],eax (pc1)
    o += b'\x8b\x47\x04'                         # eax = lo
    o += b'\x89\x85\xb0\xfe\xff\xff'             # mov [ebp-0x150],eax
    o += b'\x8b\x57\x09\x81\xe2\xff\xff\xff\x00'                         # edx = hi
    o += b'\x85\xd2'                             # test edx,edx
    hip = len(o)
    o += b'\x75\x00'                             # jnz hipath (patched below)
    o += b'\x31\xc9'                             # xor ecx,ecx
    o += b'\x8b\x85\xb4\xfe\xff\xff'             # eax = pc1
    o += b'\x8b\x95\xb0\xfe\xff\xff'             # edx = lo
    loop = len(o)
    o += b'\x39\x94\x88' + struct.pack('<i', THR - pc1)  # cmp edx,[eax+ecx*4+thr]
    o += b'\x72\x06'                             # jb done
    o += b'\x41'                                 # inc ecx
    o += b'\x83\xf9\x08'                         # cmp ecx,8
    o += b'\x72\xf1'                             # jb loop (rel8 back)
    done = len(o)
    o += b'\xeb\x00'                             # jmp done2 (patched below)
    # hipath:
    hipos = len(o)
    o[hip + 1] = hipos - (hip + 2)
    o += b'\x8b\x85\xb0\xfe\xff\xff'             # eax = lo
    o += b'\xb9\x08\x00\x00\x00'                 # ecx = 8
    o += b'\x83\xfa\x02'                         # cmp edx,2
    o += b'\x77\x09'                             # ja is10
    o += b'\x72\x0e'                             # jb done2 (fixup below)
    o += b'\x3d\x00\xe4\x0b\x54'                 # cmp eax,0x540BE400
    o += b'\x72\x07'                             # jb done2 (fixup below)
    o += b'\xb9\x09\x00\x00\x00'                 # ecx = 9
    done2 = len(o)
    o[done + 1] = done2 - (done + 2)
    # fix the two jb-done2 rel8 (computed)
    # positions: 'jb done2' after ja-is10 at hipos+6+5+3+2=hipos+16 -> target done2
    o[hipos + 17] = done2 - (hipos + 18)
    o[hipos + 24] = done2 - (hipos + 25)
    # name lookup
    o += b'\x8b\x85\xb4\xfe\xff\xff'             # eax = pc1
    o += b'\x0f\xb6\x8c\x08' + struct.pack('<i', OFFS - pc1)  # movzx ecx,[eax+ecx+offs]
    o += b'\x8d\x90' + struct.pack('<i', NAMES - pc1)         # lea edx,[eax+names]
    o += b'\x03\xd1'                             # add edx,ecx
    o += b'\x89\x54\x24\x08'                     # mov [esp+8],edx (tier)
    o += b'\x8d\x8d\xe8\xfe\xff\xff'             # lea ecx,[ebp-0x118]
    o += b'\x89\x4c\x24\x0c'                     # mov [esp+0xc],ecx
    o += b'\x8d\x85\x08\xff\xff\xff'             # lea eax,[ebp-0xf8] (label[64])
    o += b'\x89\x04\x24'                         # mov [esp],eax
    base2, pc2 = pc_add(r + len(o)); o += base2
    o += b'\x8d\x88' + struct.pack('<I', FMTD)
    o += b'\x89\x4c\x24\x04'
    o += jmp32(r + len(o), 0x1e75)
    return bytes(o)

CD2 = put_code(build_D2(dcap))
assert struct.pack('<i', THR - (CD2 + 5)) in d[fdata(CD2):fdata(dcap)]
assert struct.pack('<i', OFFS - (CD2 + 5)) in d[fdata(CD2):fdata(dcap)]
assert struct.pack('<i', NAMES - (CD2 + 5)) in d[fdata(CD2):fdata(dcap)]
assert b'\x8d\x85\x08\xff\xff\xff' in d[fdata(CD2):fdata(dcap)]
jmp_site(0x1e60, CD2, 21)

# ---------- Cave_E: draw-log hi ----------
def build_E(r):
    o = bytearray(b'\x8b\x47\x04\x89\x44\x24\x0c')
    o += b'\x8b\x47\x09\x81\xe0\xff\xff\xff\x00\x89\x44\x24\x10'
    o += b'\x8b\x07\x89\x44\x24\x08'
    base, pc = pc_add(r + len(o)); o += base
    o += b'\x8d\x88' + struct.pack('<I', FMTE)
    o += b'\x89\x4c\x24\x04'
    o += jmp32(r + len(o) + 5, 0x1ee4)
    return bytes(o)
CE = put_code(build_E(dcap))
jmp_site(0x1ecf, CE, 21)

# ---------- .data +x ----------
pe = struct.unpack('<I', bytes(d[0x3c:0x40]))[0]
nsec = struct.unpack('<H', bytes(d[pe+6:pe+8]))[0]
optsz = struct.unpack('<H', bytes(d[pe+20:pe+22]))[0]
off = pe + 24 + optsz
for i in range(nsec):
    s = off + i * 40
    if d[s:s+5] == b'.data':
        ch = struct.unpack('<I', bytes(d[s+36:s+40]))[0]
        assert ch == 0xc0000040, hex(ch)
        d[s+36:s+40] = struct.pack('<I', ch | 0x20000000)
        print('.data chars ->', hex(ch | 0x20000000))
        break

print(f'caves S={hex(CS)} A={hex(CA)} B={hex(CB)} C={hex(CC)} D1={hex(CD1)} D2={hex(CD2)} E={hex(CE)}')
print(f'data used thru {hex(dcap)} (slack ends 0x4200)')
print(f'rdata used thru {hex(rcap)} (slack ends 0x5a00)')
open(SRC, 'wb').write(bytes(d))
assert hashlib.sha256(d).hexdigest() == PATCHED_SHA256, 'patched dll sha256 mismatch'
print('WROTE', SRC)

# ---------- verify: disassemble patched heads ----------
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True
code = bytes(d[0x400:0x400+0x3000])
for va in (0x65c827dc, 0x65c827f0, 0x65c8282d, 0x65c828b6,
           0x65c81d7a, 0x65c81e60, 0x65c81ecf):
    ins = next(md.disasm(code[va-0x65c81000:va-0x65c81000+8], va))
    assert ins.mnemonic == 'jmp', (hex(va), ins.mnemonic)
    print(f'{hex(va)} -> jmp {ins.op_str} OK')
for va, b in ((0x65c82783, '8d4b0f'), (0x65c827bc, 'b908000000'),
              (0x65c82823, '0f954608'), (0x65c81d31, '807f0801'),
              (0x65c81f34, '8d8508ffffff')):
    f = va - 0x65c81000 + 0x400
    assert bytes(d[f:f+len(bytes.fromhex(b))]).hex() == b, hex(va)
    print(f'{hex(va)} inline OK')

d1 = list(md.disasm(bytes(d[fdata(CD1):fdata(CD2)]), IMG + CD1))
assert [ins.mnemonic for ins in d1] == [
    'mov', 'push', 'push', 'mov', 'mov', 'shr', 'lea', 'mov',
    'xor', 'mov', 'xchg', 'div', 'xchg', 'div', 'dec', 'add',
    'mov', 'mov', 'or', 'jne', 'lea', 'mov', 'mov', 'inc', 'inc',
    'test', 'jne', 'pop', 'pop', 'jmp'
]
assert d1[19].operands[0].imm == d1[8].address
assert d1[26].operands[0].imm == d1[21].address
assert d1[-1].operands[0].imm == IMG + 0x1d9e
assert b'%I64' not in d[frdata(NAMES):frdata(rcap)]
assert TIERS[-1].encode('gbk') + b'\x00' in d[frdata(NAMES):frdata(OFFS)]
assert b'\x89\x4e\x04\x89\xd0\xc1\xe0\x08\x09\xf8\x89\x46\x08' in \
    d[fdata(CB):fdata(CC)]
guard_code = list(md.disasm(bytes(d[ftext(CG):ftext(CG + len(guard))]), IMG + CG))
assert [ins.mnemonic for ins in guard_code] == [
    'cmp', 'jne', 'test', 'je', 'jmp', 'mov', 'shl', 'or', 'cmp',
    'jne', 'cmp', 'jne', 'jmp', 'jmp'
]
assert guard_code[3].operands[0].imm == IMG + 0x2901
assert guard_code[4].operands[0].imm == IMG + CB
assert guard_code[-2].operands[0].imm == IMG + 0x2901
assert guard_code[-1].operands[0].imm == IMG + CB
print('u64 decimal conversion and tier table OK')
print('unchanged nameplate refresh guard OK')
