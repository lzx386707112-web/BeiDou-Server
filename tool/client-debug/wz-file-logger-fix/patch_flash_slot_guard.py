#!/usr/bin/env python3
"""WzFileLogger.dll flash-slot guard patch.

Root cause
----------
The diagnostic DLL hard-codes two addresses inside WzFlashRenderer.dll:

    0x6dd05cd6  lea 0x14f0(%edi),%eax     ; edi = WzFlashRenderer base
    0x6dd05ce2  lea 0x6e088(%edi),%eax    ; -> cached as g_slot (0x6dd509e0)

`g_slot` therefore always equals `module_base + 0x6e088` (a static in the
renderer's .data).  Two sites dereference that cached pointer with only a
NULL check, so once the client unloads WzFlashRenderer (which it does on the
error-exit path) the cached pointer still looks non-NULL but its pages are
gone:

    0x6dd024ea  mov 0x6dd509e0,%ebx / test ebx,ebx / je +2 / mov (%ebx),%ebx
    0x6dd04411  mov 0x6dd509e0,%esi / test esi,esi / je ...  / mov (%esi),%esi

Observed on 2026-09-23 20:15:02, one millisecond after `ExitProcess`:

    WzFileLogger.dll+0x24f4  C0000005  read at 0x230EE088
    ebx = 0x230EE088 = WzFlashRenderer.dll (base 0x23080000) + 0x6e088

Fix
---
A validation stub is placed in the existing zero padding at the tail of
`.text` (raw file 0x5b00, RVA 0x6700 - inside the section's raw data and its
aligned page range, so it is mapped RX).  Both dereference sites call the
stub instead of reading the cached pointer directly.

    value = (g_slot != 0
             && VirtualQuery(g_slot,&mbi,sizeof mbi)
             && mbi.Type == MEM_IMAGE
             && mbi.AllocationBase == g_mod) ? *g_slot : 0

Because g_slot is always `g_mod + 0x6e088`, `AllocationBase == g_mod` is
exactly the test "the WzFlashRenderer image is still mapped".  That keeps the
guard's behaviour identical while the renderer is loaded (no false negatives)
and makes it report "no flash movie" once the module is gone, which is both
safe and correct: it also prevents the guard from tail-calling `g_flag`
(WzFlashRenderer+0x14f0), a second stale pointer into the same module.

The stub is position independent: every cross reference is a rel32 call/jump
or an EIP-relative displacement, so no relocation entry is needed even though
the DLL has DYNAMIC_BASE set.

Usage
-----
    python3 patch_flash_slot_guard.py [path/to/WzFileLogger.dll]
"""
import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, '..', '..', '..', 'clien', 'WzFileLogger.dll')
SRC = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(DEFAULT_SRC)
BAK = os.path.join(HERE, 'backup', 'WzFileLogger.dll.orig')

BASE_SHA256 = '1aa06ffb69353859b06671136c6373c9f0559d6d7c495ea5513ce832f483b53c'
PATCHED_SHA256 = '2099f66498bb0d64dcba7e183161b6405ee0476df54108bf0a0e3c746a99e217'

# ---------------------------------------------------------------- PE layout
TEXT_VA, TEXT_RAW, TEXT_VSIZE, TEXT_RSIZE = 0x1000, 0x400, 0x5630, 0x5800
DATA_VA, DATA_RAW = 0x7000, 0x5c00
IMG = 0x6dd00000

# Global variables inside WzFileLogger.dll
RVA_G_MOD = 0x509dc          # module base of the intercepted render module
RVA_G_SLOT = 0x509e0         # cached renderer .data pointer (the dangling one)
RVA_G_FLAG = 0x509e4         # cached renderer function pointer (tail-call target)
RVA_IAT_VIRTUALQUERY = 0x521f8   # KERNEL32!VirtualQuery IAT slot

# Sites that dereference the cached pointer
SITE_A, SITE_A_LEN = 0x24ea, 12
SITE_C, SITE_C_LEN = 0x4411, 14

# Code caves, carved out of the zero padding at the tail of .text
CAVE_A = 0x6640              # 10 bytes
CAVE_COMMON = 0x6650         # 84 bytes
CAVE_C = 0x66b0              # 45 bytes
CAVE_END = 0x66dd

# Expected original bytes
SITE_A_ORIG = bytes.fromhex('8b1de009d56d85db74028b1b')
SITE_C_ORIG = bytes.fromhex('8b35e009d56d85f60f8486000000')

MEM_IMAGE = 0x1000000


def ftext(rva):
    return TEXT_RAW + (rva - TEXT_VA)


def rel8(src, nxt, dst):
    d = dst - nxt
    assert -128 <= d <= 127, hex(d)
    return struct.pack('<b', d)


def rel32(src, nxt, dst):
    return struct.pack('<i', dst - nxt)


def build_stub_a(rva):
    """push eax; call COMMON; mov eax,ebx; pop eax; ret  -> preserves every
    other register, including the caller's eax/ecx/edx/esi/edi/ebp."""
    o = bytearray(b'\x50')                                    # push eax
    o += b'\xe8' + rel32(rva + 1, rva + 6, CAVE_COMMON)       # call COMMON
    o += b'\x89\xc3'                                          # mov eax,ebx
    o += b'\x58'                                              # pop eax
    o += b'\xc3'                                              # ret
    assert len(o) == 10, len(o)
    return bytes(o)


def build_common(rva):
    """Return (eax = *g_slot, CF = 0) when the cached slot is still backed by
    the recorded module image, else (eax = 0, CF = 1).  Preserves ebx, ecx,
    edx, esi, edi, ebp."""
    o = bytearray()
    o += b'\x53\x51\x52\x56\x57'                              # push ebx/ecx/edx/esi/edi
    o += b'\x83\xec\x20'                                      # sub esp,0x20
    # --- get the runtime address of ".b" into edi (position independent) ---
    o += b'\xe8\x00\x00\x00\x00'
    b_off = len(o)
    o += b'\x5f'                                              # .b: pop edi
    pc = rva + b_off
    # --- candidate = g_slot ---
    o += b'\x8b\x87' + rel32(0, 0, RVA_G_SLOT - pc)           # mov d_slot(%edi),eax
    o += b'\x85\xc0'                                          # test eax,eax
    je1 = len(o)
    o += b'\x74\x00'                                          # je bad
    o += b'\x89\xc3'                                          # mov eax,ebx (candidate)
    # --- VirtualQuery(candidate, &mbi, sizeof mbi) ---
    o += b'\x89\xe2'                                          # mov esp,edx
    o += b'\x6a\x1c'                                          # push 28
    o += b'\x52'                                              # push edx
    o += b'\x53'                                              # push ebx
    o += b'\xff\x97' + rel32(0, 0, RVA_IAT_VIRTUALQUERY - pc)  # call *d_vq(%edi)
    o += b'\x85\xc0'                                          # test eax,eax
    je2 = len(o)
    o += b'\x74\x00'                                          # je bad
    o += b'\x81\x7c\x24\x18\x00\x00\x00\x01'                  # cmp dword [esp+0x18],MEM_IMAGE
    jne1 = len(o)
    o += b'\x75\x00'                                          # jne bad
    o += b'\x8b\x97' + rel32(0, 0, RVA_G_MOD - pc)            # mov d_mod(%edi),edx
    o += b'\x39\x54\x24\x04'                                  # cmp edx,[esp+4] (AllocationBase)
    jne2 = len(o)
    o += b'\x75\x00'                                          # jne bad
    o += b'\x8b\x03'                                          # mov [ebx],eax  (*g_slot)
    o += b'\x83\xc4\x20'                                      # add esp,0x20
    o += b'\xf8'                                              # clc
    jmp1 = len(o)
    o += b'\xeb\x00'                                          # jmp done
    bad = len(o)
    o += b'\x31\xc0'                                          # xor eax,eax
    o += b'\x83\xc4\x20'                                      # add esp,0x20
    o += b'\xf9'                                              # stc
    done = len(o)
    o += b'\x5f\x5e\x5a\x59\x5b'                              # pop edi/esi/edx/ecx/ebx
    o += b'\xc3'                                              # ret
    o[je1 + 1:je1 + 2] = rel8(0, je1 + 2, bad)
    o[je2 + 1:je2 + 2] = rel8(0, je2 + 2, bad)
    o[jne1 + 1:jne1 + 2] = rel8(0, jne1 + 2, bad)
    o[jne2 + 1:jne2 + 2] = rel8(0, jne2 + 2, bad)
    o[jmp1 + 1:jmp1 + 2] = rel8(0, jmp1 + 2, done)
    assert len(o) == 84, len(o)
    return bytes(o)


def build_cave_c(rva):
    """Re-create the guard's original control flow with a validated read:
       slot unusable -> epilogue (0x44a5)
       movie == 0    -> null-movie log path (0x4425)
       movie != 0    -> tail-call the original render fn (0x4491), eax = g_flag
    """
    o = bytearray()
    o += b'\xe8' + rel32(rva, rva + 5, CAVE_COMMON)           # call COMMON
    o += b'\x0f\x82' + rel32(0, rva + 0x0b, 0x44a5)           # jc  epilogue (CF=1)
    o += b'\x85\xc0'                                          # test eax,eax
    o += b'\x0f\x84' + rel32(0, rva + 0x13, rva + 0x26)       # je  null-movie log
    o += b'\x89\xc6'                                          # mov eax,esi (movie)
    o += b'\xe8\x00\x00\x00\x00'                              # call .c2
    c2_off = len(o)
    o += b'\x58'                                              # .c2: pop eax
    pc = rva + c2_off
    o += b'\x8b\x80' + rel32(0, 0, RVA_G_FLAG - pc)           # mov d_flag(%eax),eax
    o += b'\xe9' + rel32(0, rva + 0x26, 0x4491)               # jmp tail-call
    logpath = len(o)
    o += b'\x31\xf6'                                          # xor esi,esi
    o += b'\xe9' + rel32(0, rva + 0x2d, 0x4425)               # jmp log path
    assert logpath == 0x26, hex(logpath)
    assert len(o) == 45, len(o)
    return bytes(o), logpath


def apply(path, write=True):
    cur = open(path, 'rb').read()
    sha = hashlib.sha256(cur).hexdigest()
    if sha == PATCHED_SHA256:
        print('already patched ->', path)
        return None
    assert sha == BASE_SHA256, 'unexpected input sha256: %s' % sha

    d = bytearray(cur)

    # ---------- sanity: the exact original bytes we are replacing ----------
    a = ftext(SITE_A)
    c = ftext(SITE_C)
    assert bytes(d[a:a + SITE_A_LEN]) == SITE_A_ORIG, \
        'site A mismatch @%#x: %s' % (SITE_A, bytes(d[a:a + SITE_A_LEN]).hex())
    assert bytes(d[c:c + SITE_C_LEN]) == SITE_C_ORIG, \
        'site C mismatch @%#x: %s' % (SITE_C, bytes(d[c:c + SITE_C_LEN]).hex())

    # ---------- sanity: cave area must be untouched zero padding ----------
    lo, hi = ftext(CAVE_A), ftext(0x6800)
    assert set(d[lo:hi]) == {0}, 'cave area is not clean padding'
    assert TEXT_VA + TEXT_RSIZE == 0x6800, 'text raw end changed'

    # ---------- sanity: .text VirtualSize / SizeOfCode still as expected -----
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    _mach, nsec, _ts, _sym, _nsym, optsz, _chars = struct.unpack_from(
        '<HHIIIHH', d, e_lfanew + 4)
    opt = e_lfanew + 24
    size_of_code = struct.unpack_from('<I', d, opt + 4)[0]
    assert size_of_code == TEXT_RSIZE, hex(size_of_code)
    sh_off = opt + optsz
    text_sh = None
    for i in range(nsec):
        s = sh_off + i * 40
        if bytes(d[s:s + 8]).rstrip(b'\x00') == b'.text':
            text_sh = s
            break
    assert text_sh is not None
    vsize, vaddr, rsize, rawptr = struct.unpack_from('<IIII', d, text_sh + 8)
    assert (vsize, vaddr, rsize, rawptr) == (TEXT_VSIZE, TEXT_VA, TEXT_RSIZE, TEXT_RAW), \
        (hex(vsize), hex(vaddr), hex(rsize), hex(rawptr))
    # no other section may overlap the extended .text range
    for i in range(nsec):
        s = sh_off + i * 40
        if s == text_sh:
            continue
        vs, va = struct.unpack_from('<II', d, s + 8)
        assert va == 0 or va >= TEXT_VA + TEXT_RSIZE, \
            'section %s overlaps extended .text' % d[s:s + 8].rstrip(b'\x00')

    # ---------- code caves ----------
    stub_a = build_stub_a(CAVE_A)
    common = build_common(CAVE_COMMON)
    cave_c, _ = build_cave_c(CAVE_C)
    assert CAVE_C + len(cave_c) == CAVE_END
    d[ftext(CAVE_A):ftext(CAVE_A) + len(stub_a)] = stub_a
    d[ftext(CAVE_COMMON):ftext(CAVE_COMMON) + len(common)] = common
    d[ftext(CAVE_C):ftext(CAVE_C) + len(cave_c)] = cave_c

    # ---------- call sites ----------
    d[a:a + SITE_A_LEN] = (b'\xe8' + rel32(SITE_A, SITE_A + 5, CAVE_A)
                           + b'\x90' * (SITE_A_LEN - 5))
    d[c:c + SITE_C_LEN] = (b'\xe9' + rel32(SITE_C, SITE_C + 5, CAVE_C)
                           + b'\x90' * (SITE_C_LEN - 5))

    # ---------- extend .text so the cave is inside the section ----------
    d[text_sh + 8:text_sh + 12] = struct.pack('<I', TEXT_RSIZE)

    if write:
        os.makedirs(os.path.dirname(BAK), exist_ok=True)
        if not os.path.exists(BAK):
            shutil.copy2(path, BAK)
            print('backup ->', BAK)
        with open(path, 'wb') as fh:
            fh.write(bytes(d))
        print('WROTE', path)
    return bytes(d)


def pe_checksum(data, offset):
    """Standard PE image checksum, with the checksum field treated as zero."""
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


if __name__ == '__main__':
    out = apply(SRC)
    if out is not None:
        # refresh the PE checksum so the header stays self-consistent
        e_lfanew = struct.unpack_from('<I', out, 0x3c)[0]
        cksum_off = e_lfanew + 24 + 64
        out = bytearray(out)
        out[cksum_off:cksum_off + 4] = struct.pack('<I', 0)
        out[cksum_off:cksum_off + 4] = struct.pack('<I', pe_checksum(bytes(out), cksum_off))
        with open(SRC, 'wb') as fh:
            fh.write(bytes(out))
        sha = hashlib.sha256(out).hexdigest()
        print('PATCHED_SHA256 =', sha)
        print('bytes', len(out))
