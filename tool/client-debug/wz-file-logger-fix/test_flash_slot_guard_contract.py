#!/usr/bin/env python3
"""Contract test for the WzFileLogger.dll flash-slot guard patch.

Run after patch_flash_slot_guard.py:

    /opt/homebrew/bin/python3 test_flash_slot_guard_contract.py \
        [patched.dll] [original.dll]

(capstone is required; it lives in the homebrew interpreter, not in the
managed venv used by the patcher itself.)

Checks (all static, no Windows needed):
  1. the byte diff against the original touches exactly the expected ranges;
  2. the extended .text still does not overlap any other section;
  3. both call sites and the three code caves disassemble exactly as designed;
  4. every branch/call target and data reference inside the stub is correct;
  5. the PE checksum matches the standard algorithm;
  6. the original unguarded read is really gone from both sites.
"""
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PATCHED = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(ROOT, 'clien', 'WzFileLogger.dll')
ORIGINAL = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else \
    os.path.join(HERE, 'backup', 'WzFileLogger.dll.orig')

from capstone import Cs, CS_ARCH_X86, CS_MODE_32  # noqa: E402
from capstone.x86 import X86_OP_REG, X86_OP_MEM  # noqa: E402

IMG = 0x6dd00000
TEXT_VA, TEXT_RAW, TEXT_RSIZE = 0x1000, 0x400, 0x5800
BASE_SHA256 = '1aa06ffb69353859b06671136c6373c9f0559d6d7c495ea5513ce832f483b53c'

SITE_A, SITE_A_LEN = 0x24ea, 12
SITE_C, SITE_C_LEN = 0x4411, 14
CAVE_A, CAVE_A_LEN = 0x6640, 10
CAVE_COMMON, CAVE_COMMON_LEN = 0x6650, 84
CAVE_C, CAVE_C_LEN = 0x66b0, 45

RVA_G_MOD, RVA_G_SLOT, RVA_G_FLAG, RVA_IAT_VQ = 0x509dc, 0x509e0, 0x509e4, 0x521f8

ftext = lambda rva: TEXT_RAW + (rva - TEXT_VA)
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True


def dis(p, rva, length):
    ins = list(md.disasm(p[ftext(rva):ftext(rva) + length], IMG + rva))
    assert ins, 'nothing disassembled at %#x' % rva
    assert ins[-1].address + ins[-1].size == IMG + rva + length, \
        'undecoded trailing bytes at %#x' % rva
    return ins


def ops(ins):
    """Intel-syntax operand view: ('reg','eax') | ('mem',(base,disp)) | ('imm',v)."""
    out = []
    for op in ins.operands:
        if op.type == X86_OP_REG:
            out.append(('reg', ins.reg_name(op.reg)))
        elif op.type == X86_OP_MEM:
            base = ins.reg_name(op.mem.base) if op.mem.base else ''
            out.append(('mem', (base, op.mem.disp)))
        else:
            out.append(('imm', op.imm))
    return out


def main():
    p = open(PATCHED, 'rb').read()
    o = open(ORIGINAL, 'rb').read()
    assert hashlib.sha256(o).hexdigest() == BASE_SHA256, \
        'original backup is not the expected baseline'
    assert len(p) == len(o), 'file size changed: %d -> %d' % (len(o), len(p))

    # ---------- PE headers ----------
    e = struct.unpack_from('<I', p, 0x3c)[0]
    _m, nsec, _t, _s, _n, optsz, _c = struct.unpack_from('<HHIIIHH', p, e + 4)
    sh_off = e + 24 + optsz
    secs, text_sh = {}, None
    for i in range(nsec):
        s = sh_off + i * 40
        nm = p[s:s + 8].rstrip(b'\x00').decode()
        secs[nm] = struct.unpack_from('<IIII', p, s + 8)
        if nm == '.text':
            text_sh = s

    # ---------- 1. byte diff map ----------
    allowed = [
        (ftext(SITE_A), ftext(SITE_A) + SITE_A_LEN - 1),
        (ftext(SITE_C), ftext(SITE_C) + SITE_C_LEN - 1),
        (ftext(CAVE_A), ftext(CAVE_A) + CAVE_A_LEN - 1),
        (ftext(CAVE_COMMON), ftext(CAVE_COMMON) + CAVE_COMMON_LEN - 1),
        (ftext(CAVE_C), ftext(CAVE_C) + CAVE_C_LEN - 1),
        (text_sh + 8, text_sh + 11),          # .text VirtualSize
        (e + 24 + 64, e + 24 + 67),           # optional header CheckSum
    ]
    ranges = []
    for i in range(len(p)):
        if p[i] != o[i]:
            if ranges and i == ranges[-1][1] + 1:
                ranges[-1][1] = i
            else:
                ranges.append([i, i])
    for lo, hi in ranges:
        inside = any(a <= lo and hi <= b for a, b in allowed)
        print('   diff 0x%04x..0x%04x   rva 0x%04x..0x%04x   %s'
              % (lo, hi, lo - TEXT_RAW + TEXT_VA, hi - TEXT_RAW + TEXT_VA,
                 'OK' if inside else '*** UNEXPECTED ***'))
        assert inside, 'unexpected diff range 0x%04x..0x%04x' % (lo, hi)
    print('1. byte diff limited to the declared ranges (%d range(s)): OK'
          % len(ranges))

    # ---------- 2. section layout ----------
    assert secs['.text'][0] == TEXT_RSIZE, hex(secs['.text'][0])
    assert secs['.text'][2] == TEXT_RSIZE, hex(secs['.text'][2])
    assert secs['.data'][1] >= TEXT_VA + TEXT_RSIZE, hex(secs['.data'][1])
    assert CAVE_C + CAVE_C_LEN <= TEXT_VA + TEXT_RSIZE
    print('2. .text 0x%x..0x%x (RX), .data @0x%x, no overlap: OK'
          % (TEXT_VA, TEXT_VA + TEXT_RSIZE, secs['.data'][1]))

    # ---------- 3. call sites ----------
    a = dis(p, SITE_A, SITE_A_LEN)
    assert [i.mnemonic for i in a] == ['call'] + ['nop'] * 7, [i.mnemonic for i in a]
    assert ops(a[0])[0] == ('imm', IMG + CAVE_A), ops(a[0])
    c = dis(p, SITE_C, SITE_C_LEN)
    assert [i.mnemonic for i in c] == ['jmp'] + ['nop'] * 9, [i.mnemonic for i in c]
    assert ops(c[0])[0] == ('imm', IMG + CAVE_C), ops(c[0])
    print('3. site A (0x%x) -> call 0x%x ; site C (0x%x) -> jmp 0x%x: OK'
          % (SITE_A, IMG + CAVE_A, SITE_C, IMG + CAVE_C))

    # ---------- 4a. stub A ----------
    sa = dis(p, CAVE_A, CAVE_A_LEN)
    assert [i.mnemonic for i in sa] == ['push', 'call', 'mov', 'pop', 'ret'], \
        [i.mnemonic for i in sa]
    assert ops(sa[0])[0] == ('reg', 'eax')
    assert ops(sa[1])[0] == ('imm', IMG + CAVE_COMMON)
    assert ops(sa[2]) == [('reg', 'ebx'), ('reg', 'eax')], ops(sa[2])
    assert ops(sa[3])[0] == ('reg', 'eax')
    print('4a. stub A = push eax; call common; mov ebx,eax; pop eax; ret '
          '(everything else preserved): OK')

    # ---------- 4b. common validator ----------
    cm = dis(p, CAVE_COMMON, CAVE_COMMON_LEN)
    want = ['push'] * 5 + ['sub', 'call', 'pop', 'mov', 'test', 'je', 'mov',
                           'mov', 'push', 'push', 'push', 'call', 'test', 'je',
                           'cmp', 'jne', 'mov', 'cmp', 'jne', 'mov', 'add',
                           'clc', 'jmp', 'xor', 'add', 'stc'] + ['pop'] * 5 + ['ret']
    assert [i.mnemonic for i in cm] == want, [i.mnemonic for i in cm]
    assert [ops(cm[i])[0] for i in range(5)] == \
        [('reg', r) for r in ('ebx', 'ecx', 'edx', 'esi', 'edi')]
    assert [ops(cm[i])[0] for i in range(31, 36)] == \
        [('reg', r) for r in ('edi', 'esi', 'edx', 'ecx', 'ebx')]
    pc = IMG + CAVE_COMMON + 0x0d          # runtime address of ".b" (edi)
    assert ops(cm[8])[0] == ('reg', 'eax'), ops(cm[8])
    assert ops(cm[8])[1] == ('mem', ('edi', (IMG + RVA_G_SLOT) - pc)), ops(cm[8])
    assert ops(cm[16])[0] == ('mem', ('edi', (IMG + RVA_IAT_VQ) - pc)), ops(cm[16])
    assert ops(cm[19]) == [('mem', ('esp', 0x18)), ('imm', 0x1000000)], ops(cm[19])
    assert ops(cm[21]) == [('reg', 'edx'), ('mem', ('edi', (IMG + RVA_G_MOD) - pc))], \
        ops(cm[21])
    assert ops(cm[22]) == [('mem', ('esp', 0x04)), ('reg', 'edx')], ops(cm[22])
    assert ops(cm[13])[0] == ('imm', 0x1c)          # sizeof(MBI)
    assert ops(cm[24]) == [('reg', 'eax'), ('mem', ('ebx', 0))], ops(cm[24])
    bad = IMG + CAVE_COMMON + 0x48
    for idx in (10, 18, 20, 23):
        assert ops(cm[idx])[0] == ('imm', bad), (idx, cm[idx].op_str)
    assert cm[26].mnemonic == 'clc'
    assert ops(cm[27])[0] == ('imm', IMG + CAVE_COMMON + 0x4e)
    assert ops(cm[28])[0] == ('reg', 'eax')
    assert cm[30].mnemonic == 'stc'
    assert [i.mnemonic for i in cm[-5:]] == ['pop'] * 4 + ['ret']
    print('4b. common: g_slot != 0 -> VirtualQuery(g_slot,&mbi,28) -> '
          'mbi.Type==MEM_IMAGE -> mbi.AllocationBase==g_mod -> read *g_slot; '
          'else 0. CF set after the last flag clobber, survives the pops: OK')

    # ---------- 4c. cave C ----------
    cc = dis(p, CAVE_C, CAVE_C_LEN)
    assert [i.mnemonic for i in cc] == ['call', 'jb', 'test', 'je', 'mov',
                                        'call', 'pop', 'mov', 'jmp', 'xor', 'jmp'], \
        [i.mnemonic for i in cc]
    assert ops(cc[0])[0] == ('imm', IMG + CAVE_COMMON)
    assert ops(cc[1])[0] == ('imm', IMG + 0x44a5)     # unusable -> epilogue
    assert ops(cc[3])[0] == ('imm', IMG + CAVE_C + 0x26)  # movie == 0 -> log
    assert ops(cc[4]) == [('reg', 'esi'), ('reg', 'eax')], ops(cc[4])
    assert ops(cc[8])[0] == ('imm', IMG + 0x4491)     # movie != 0 -> tail-call
    assert ops(cc[10])[0] == ('imm', IMG + 0x4425)
    c2pc = IMG + CAVE_C + 0x1a
    assert ops(cc[7]) == [('reg', 'eax'), ('mem', ('eax', (IMG + RVA_G_FLAG) - c2pc))], \
        ops(cc[7])
    print('4c. cave C: unusable -> 0x44a5, null movie -> 0x4425, live movie -> '
          '0x4491 with eax = g_flag: OK')

    # ---------- 5. PE checksum ----------
    cksum_off = e + 24 + 64
    stored = struct.unpack_from('<I', p, cksum_off)[0]
    d = bytearray(p)
    d[cksum_off:cksum_off + 4] = b'\x00' * 4
    total, length = 0, len(d)
    for i in range(0, length, 2):
        total = (total + (d[i] | (d[i + 1] << 8))) & 0xffffffff
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    assert stored == (total + length) & 0xffffffff, \
        'checksum %#x != %#x' % (stored, (total + length) & 0xffffffff)
    print('5. PE checksum 0x%x consistent: OK' % stored)

    # ---------- 6. the unguarded reads are really gone ----------
    orig = dis(o, SITE_A, SITE_A_LEN)
    assert any(i.mnemonic == 'mov' and i.op_str.endswith('[ebx]') for i in orig), \
        'baseline did not contain the crashing read'
    for site, ln in ((SITE_A, SITE_A_LEN), (SITE_C, SITE_C_LEN)):
        blob = p[ftext(site):ftext(site) + ln]
        assert b'\x8b\x1b' not in blob and b'\x8b\x36' not in blob
    print('6. the unguarded `mov (%reg),%reg` reads are gone from both sites: OK')
    print()
    print('ALL CONTRACT CHECKS PASSED for', PATCHED)
    print('sha256 =', hashlib.sha256(p).hexdigest())


if __name__ == '__main__':
    main()
