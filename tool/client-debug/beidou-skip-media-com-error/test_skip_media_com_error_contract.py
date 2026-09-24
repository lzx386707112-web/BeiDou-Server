#!/usr/bin/env python3
"""Contract test for the BeiDou.exe "skip media _com_error" patch.

Run after `patch_skip_media_com_error.py --apply`:

    /opt/homebrew/bin/python3 test_skip_media_com_error_contract.py

Verifies, byte by byte and by disassembly:

  1. exactly one code byte changed (0x403ae9: 0x7d -> 0xeb) plus the PE
     checksum field; every other byte is identical to the backup;
  2. the patched jcc is now an unconditional `jmp 0x403af7`;
  3. `_com_raise_error` (0xa5fdf2) is unreachable from the whole function
     body 0x403a93..0x403b26;
  4. no instruction anywhere in .text branches into the now-dead throw block
     0x403aeb..0x403af6;
  5. the fall-through target 0x403af7 is still the function's normal
     continuation (`mov ecx,[ebp+8]` ... `ret 0x10`);
  6. the PE header is self-consistent (checksum field matches a fresh
     recomputation, sections/file size unchanged).
"""
import hashlib
import os
import struct
import sys

try:
    import capstone
except ImportError:  # pragma: no cover
    print('capstone is required: /opt/homebrew/bin/python3 -m pip install capstone')
    raise SystemExit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TARGET = os.path.join(REPO, 'clien', 'BeiDou.exe')
BACKUP = os.path.join(HERE, 'backup', 'BeiDou.exe.orig')

IMAGEBASE = 0x400000
TEXT_VA, TEXT_RAW, TEXT_RSIZE = 0x401000, 0x1000, 0x6EF000
E8_END = TEXT_VA + TEXT_RSIZE

SITE_VA = 0x403AE9
CONT_VA = 0x403AF7
DEAD_LO, DEAD_HI = 0x403AEB, 0x403AF7
FUNC_LO, FUNC_HI = 0x403A93, 0x403B26
THROW_CALLEE = 0xA5FDF2

BASE_SHA256 = '06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18'

failures = []


def check(cond, msg):
    print(('  ok   ' if cond else '  FAIL ') + msg)
    if not cond:
        failures.append(msg)


def foff(va):
    return TEXT_RAW + (va - TEXT_VA)


def pe_checksum(data, offset):
    d = bytearray(data)
    d[offset:offset + 4] = b'\x00\x00\x00\x00'
    total = 0
    length = len(d)
    if length % 2:
        d += b'\x00'
        length += 1
    for i in range(0, length, 2):
        total += d[i] | (d[i + 1] << 8)
        total = (total & 0xffff) + (total >> 16)
    total = (total & 0xffff) + (total >> 16)
    return (total + length) & 0xffffffff


def linear_sweep(d):
    """Disassemble .text linearly and yield capstone instructions.

    Naive linear sweep: decoding may drift, so only relative-branch targets are
    consumed (used to prove a *negative*), never used as the sole evidence."""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    code = bytes(d[TEXT_RAW:TEXT_RAW + TEXT_RSIZE])
    for ins in md.disasm(code, TEXT_VA):
        yield ins


def reachable(insns, entry, lo, hi):
    """Control-flow reachability over an instruction stream.

    Follows fall-through and direct branch targets, stops at `ret`, ignores
    anything outside [lo,hi).  Returns the set of reachable instruction
    addresses.  This is what proves the throw block is dead: its bytes remain,
    but nothing can get to them."""
    by_addr = {i.address: i for i in insns}
    seen, stack = set(), [entry]
    while stack:
        a = stack.pop()
        if a in seen or not (lo <= a < hi):
            continue
        i = by_addr.get(a)
        if i is None:
            continue
        seen.add(a)
        nxt = a + i.size
        m = i.mnemonic
        if m.startswith('ret'):
            continue
        if m == 'jmp':
            try:
                t = int(i.op_str, 16)
            except ValueError:
                continue                       # indirect: not statically known
            if lo <= t < hi:
                stack.append(t)
            continue
        if m.startswith('j'):                  # conditional: both edges
            try:
                t = int(i.op_str, 16)
            except ValueError:
                t = None
            if t is not None and lo <= t < hi:
                stack.append(t)
        if lo <= nxt < hi:
            stack.append(nxt)
    return seen


def reachability_report(d):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    body = list(md.disasm(bytes(d[foff(FUNC_LO):foff(FUNC_HI)]), FUNC_LO))
    seen = reachable(body, FUNC_LO, FUNC_LO, FUNC_HI)
    dead = sorted(hex(a) for a in seen if DEAD_LO <= a < DEAD_HI)
    throws = sorted(hex(i.address) for i in body
                    if i.address in seen and i.mnemonic == 'call'
                    and hex(THROW_CALLEE) in i.op_str)
    return seen, dead, throws


def main():
    cur = open(TARGET, 'rb').read()
    base = open(BACKUP, 'rb').read()

    print('== files ==')
    check(len(cur) == len(base), 'file size unchanged (%d)' % len(cur))
    check(hashlib.sha256(base).hexdigest() == BASE_SHA256,
          'backup is the pristine baseline')

    e_lfanew = struct.unpack_from('<I', cur, 0x3c)[0]
    opt = e_lfanew + 24
    optsz = struct.unpack_from('<H', cur, e_lfanew + 20)[0]
    cksum_off = opt + 64

    print('== diff scope ==')
    diff = [i for i, (a, b) in enumerate(zip(base, cur)) if a != b]
    print('     changed offsets:', ['%#x' % i for i in diff])
    check(foff(SITE_VA) in diff, 'patch site 0x403ae9 changed')
    code_only = [i for i in diff if not (cksum_off <= i < cksum_off + 4)]
    check(code_only == [foff(SITE_VA)],
          'exactly one non-header byte changed, and it is the patch site')

    print('== patched instruction ==')
    check(cur[foff(SITE_VA)] == 0xEB, '0x403ae9 is now 0xeb (jmp rel8)')
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    win = bytes(cur[foff(0x403AE4):foff(0x403AE4) + 19])
    insns = list(md.disasm(win, 0x403AE4))
    for i in insns:
        print('     %#x: %-6s %s' % (i.address, i.mnemonic, i.op_str))
    check(insns[0].mnemonic == 'call', 'window starts with the COM call')
    j = [i for i in insns if i.address == SITE_VA]
    check(len(j) == 1 and j[0].mnemonic == 'jmp',
          '0x403ae9 decodes as an unconditional jmp')
    if j:
        check(j[0].op_str == hex(CONT_VA), 'jmp target is %#x' % CONT_VA)

    print('== throw is DEAD (control-flow reachability) ==')
    seen_now, dead_now, throws_now = reachability_report(cur)
    seen_before, dead_before, throws_before = reachability_report(base)
    print('     reachable instrs: before=%d after=%d' % (len(seen_before), len(seen_now)))
    print('     reachable in throw block: before=%s after=%s'
          % (dead_before or 'none', dead_now or 'none'))
    print('     reachable _com_raise_error calls: before=%s after=%s'
          % (throws_before or 'none', throws_now or 'none'))
    verify = 0x403AE7
    check(verify in seen_now, 'sanity: 0x403ae7 (test eax,eax) is reachable')
    check(CONT_VA in seen_now, 'sanity: continuation 0x403af7 is reachable')
    check(bool(throws_before), 'baseline: the throw WAS reachable (patch has effect)')
    check(not throws_now,
          '_com_raise_error(0xa5fdf2) is now UNREACHABLE from 0x403a93')
    check(not dead_now, 'nothing in 0x403aeb..0x403af6 is reachable any more')

    dead_targets = []
    for i in linear_sweep(cur):
        if i.mnemonic.startswith('j'):
            try:
                t = int(i.op_str, 16)
            except ValueError:
                continue
            if DEAD_LO <= t < DEAD_HI:
                dead_targets.append((hex(i.address), i.mnemonic, i.op_str))
    check(not dead_targets,
          'no branch anywhere in .text enters 0x403aeb..0x403af6 %s'
          % (dead_targets or ''))

    print('== continuation still intact ==')
    cont = list(md.disasm(bytes(cur[foff(CONT_VA):foff(CONT_VA) + 12]), CONT_VA))
    print('     %#x: %-6s %s' % (cont[0].address, cont[0].mnemonic, cont[0].op_str))
    check(cont[0].mnemonic == 'mov' and 'ebp' in cont[0].op_str,
          '%#x is still the normal continuation (mov ecx,[ebp+0x8])' % CONT_VA)
    tail = bytes(cur[foff(FUNC_HI - 4):foff(FUNC_HI)])
    check(tail == bytes.fromhex('c2 10 00 56'),
          'function epilogue unchanged (ret 0x10)')
    check(bytes(cur[foff(0x403AEB):foff(0x403AF6)]) ==
          bytes(base[foff(0x403AEB):foff(0x403AF6)]),
          'dead throw block bytes preserved verbatim')

    print('== PE header ==')
    check(struct.unpack_from('<I', cur, opt + 28)[0] == IMAGEBASE,
          'ImageBase still 0x400000')
    check(struct.unpack_from('<H', cur, opt + 70)[0] == 0x0000,
          'DllCharacteristics still 0x0000 (no DYNAMIC_BASE / no integrity check)')
    nsec = struct.unpack_from('<H', cur, e_lfanew + 6)[0]
    check(nsec == struct.unpack_from('<H', base, e_lfanew + 6)[0],
          'section count unchanged')
    sh = opt + optsz
    for i in range(nsec):
        s = sh + i * 40
        for off, ln in ((8, 4), (12, 4), (16, 4), (20, 4)):
            check(cur[s + off:s + off + ln] == base[s + off:s + off + ln],
                  'section %d header[%d] unchanged'
                  % (i, off))
    stored = struct.unpack_from('<I', cur, cksum_off)[0]
    fresh = pe_checksum(cur, cksum_off)
    check(stored == fresh, 'PE checksum self-consistent (%#x)' % stored)
    check(stored != 0, 'PE checksum is non-zero')

    print()
    print('patched sha256 =', hashlib.sha256(cur).hexdigest())
    if failures:
        print('\n%d CHECK(S) FAILED' % len(failures))
        return 1
    print('ALL CHECKS PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
