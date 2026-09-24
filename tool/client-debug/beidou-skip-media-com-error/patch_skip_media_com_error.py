#!/usr/bin/env python3
"""BeiDou.exe - 媒体/资源加载失败时跳过播放，不再抛 _com_error。

Root cause
----------
2026-09-23 20:11 会话的 first-chance 日志里出现 3 次同一个 C++ 异常
(`code=0xe06d7363` = magic `0x19930520`，即 MSVC 的 `_com_error`)，
随后客户端弹错误框并 ExitProcess(0)：

    HRESULT = 0x80030002  STG_E_FILENOTFOUND
    IID     = 0x00bd8318  {57DFE40B-3E20-4DBC-97E8-805A50F381BF}

抛点就是 BeiDou.exe 里这个通用 COM 包装函数（0x403a93）：

    403ae4  ff 51 1c          call dword ptr [ecx+0x1c]   ; 媒体/资源接口虚调用
    403ae7  85 c0             test eax,eax
    403ae9  7d 0c             jge  0x403af7                ; S_OK -> 跳过抛出
    403aeb  68 18 83 bd 00    push 0x00bd8318             ; riid（硬编码 IID 常量）
    403af0  53                push ebx                    ; pUnk = 0x0a769604
    403af1  50                push eax                    ; hr   = 0x80030002
    403af2  e8 fb c2 65 00    call 0xa5fdf2               ; _com_raise_error -> 抛 _com_error
    403af7  8b 4d 08          mov  ecx,[ebp+0x8]          ; 正常收尾（成功路径也走这里）

`0xa5fdf2` 反汇编确认是 `_com_raise_error(hr, pUnk, riid)`：它先 QueryInterface
拿 IErrorInfo，再构造 `_com_error` 并 `_CxxThrowException`。该异常被上层 catch
后弹框（用户截图里的 -2147287038）并结束进程。

为什么 1 字节就够
----------------
把 0x403ae9 的 `jge +0xc`（0x7d）改成长跳 `jmp +0xc`（0xeb），
成功路径与失败路径都落到 0x403af7 的正常收尾。失败时不再抛异常，
而是让调用链自然把它当成"没有可用对象"：

  * F_A 的 16 字节出参 `[ebp-0x20]` 在 0x403ab1 已由
    `call dword ptr [0xaf0268]`（`_variant_t` 构造）初始化为空；
  * 0x403af7 -> `call 0x4039ac` 只是 `memcpy(dst, src, 16)` + 清源
    （0x4039d5 分支，3 参为 0），与成败无关，不会解引用空指针；
  * 调用方 0x5cad06 对返回值有专门的空值分支：
        5cad0b  cmp eax,ebx(0)
        5cad13  je  0x5cad36     -> mov ebx,0x80004002 (E_NOINTERFACE)，
                                   走 0x5cad36 起的正常清理，全程不再 throw。

（`0x4032b2` 在空 VARIANT 上走 `cmp BYTE PTR [ebp+0xc],0` -> `xor eax,eax`，
 `[ebp+0xc]` 来自 0x5cacc0 的 `push ebx`（ebx=0），确定为 0。）

0x403aeb..0x403af6 没有任何分支进入（已全量扫描 rel8/rel32 目标确认），
所以这段抛出代码改成不可达是安全的；本补丁保留其原始字节，仅改 1 字节，
便于回退与比对。

Usage
-----
    python3 patch_skip_media_com_error.py --dry-run     # 只校验，不落盘
    python3 patch_skip_media_com_error.py --apply       # 落盘（先备份）
    python3 patch_skip_media_com_error.py <other.exe> --apply
"""
import hashlib
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.join(HERE, '..', '..', '..', 'clien', 'BeiDou.exe')
BAK = os.path.join(HERE, 'backup', 'BeiDou.exe.orig')

BASE_SHA256 = '06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18'

# ------------------------------------------------------------------ PE layout
IMAGEBASE = 0x00400000
TEXT_VA, TEXT_RAW = 0x401000, 0x1000
TEXT_RSIZE = 0x6EF000

# ------------------------------------------------------------------ patch site
SITE_VA = 0x403AE9          # the `jge +0xc`
SITE_ORIG = 0x7D            # jge rel8
SITE_PATCHED = 0xEB         # jmp rel8

# 19-byte context window starting at 0x403AE4, used as a fingerprint
CTX_VA = 0x403AE4
CTX_ORIG = bytes.fromhex('ff 51 1c 85 c0 7d 0c 68 18 83 bd 00 53 50 e8 fb c2 65 00')
CTX_PATCHED = bytes.fromhex('ff 51 1c 85 c0 eb 0c 68 18 83 bd 00 53 50 e8 fb c2 65 00')

# dead throw code that must stay byte-identical (0x403aeb..0x403af6)
DEAD_VA = 0x403AEB
DEAD_ORIG = bytes.fromhex('68 18 83 bd 00 53 50 e8 fb c2 65 00')

# branch targets into the throw block would make the patch unsound
FORBIDDEN_TARGETS = range(DEAD_VA, 0x403AF7)
THROW_CALLEE = 0xA5FDF2     # _com_raise_error


def foff(va):
    return TEXT_RAW + (va - TEXT_VA)


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


def pe_layout(d):
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    assert d[e_lfanew:e_lfanew + 4] == b'PE\x00\x00', 'not a PE image'
    _mach, nsec, _ts, _sym, _nsym, optsz, _chars = struct.unpack_from(
        '<HHIIIHH', d, e_lfanew + 4)
    opt = e_lfanew + 24
    cksum_off = opt + 64
    return e_lfanew, nsec, opt, optsz, cksum_off


def scan_branch_targets(d, lo_va, hi_va):
    """Return every rel8/rel32 branch target that lands in [lo,hi).

    A deliberately conservative linear sweep: it walks .text decoding the two
    relative branch encodings plus the `0f 8x` long forms, and collects their
    destinations.  False positives (targets decoded out of data) are harmless
    here because the answer is used only as a "must be empty" assertion on a
    small, well-formed code range.
    """
    hits = []
    start, end = foff(TEXT_VA), foff(TEXT_VA + TEXT_RSIZE)
    i = start
    while i < end - 1:
        b = d[i]
        # e8/e9 rel32
        if b in (0xE8, 0xE9) and i + 5 <= end:
            rel = struct.unpack_from('<i', d, i + 1)[0]
            tgt = TEXT_VA + (i - start) + 5 + rel
            if lo_va <= tgt < hi_va:
                hits.append((TEXT_VA + (i - start), tgt))
            i += 5
            continue
        # 0f 8x rel32
        if b == 0x0F and i + 6 <= end and (d[i + 1] & 0xF0) == 0x80:
            rel = struct.unpack_from('<i', d, i + 2)[0]
            tgt = TEXT_VA + (i - start) + 6 + rel
            if lo_va <= tgt < hi_va:
                hits.append((TEXT_VA + (i - start), tgt))
            i += 6
            continue
        # 7x rel8 (jcc/jmp short)
        if 0x70 <= b <= 0x7F and i + 2 <= end:
            rel = struct.unpack_from('<b', d, i + 1)[0]
            tgt = TEXT_VA + (i - start) + 2 + rel
            if lo_va <= tgt < hi_va:
                hits.append((TEXT_VA + (i - start), tgt))
            i += 2
            continue
        i += 1
    return hits


def apply(path, write=True):
    cur = open(path, 'rb').read()
    sha = hashlib.sha256(cur).hexdigest()
    d = bytearray(cur)

    e_lfanew, nsec, opt, optsz, cksum_off = pe_layout(d)
    image_base = struct.unpack_from('<I', d, opt + 28)[0]
    checksum = struct.unpack_from('<I', d, cksum_off)[0]
    dllchars = struct.unpack_from('<H', d, opt + 70)[0]
    size_of_image = struct.unpack_from('<I', d, opt + 56)[0]
    print('input   :', path)
    print('sha256  :', sha)
    print('size    :', len(d))
    print('imagebse: %#x (fixed=%s)  sizeofimage=%#x  dllchars=%#x  cksum=%#x'
          % (image_base, image_base == IMAGEBASE and 'yes' or 'NO',
             size_of_image, dllchars, checksum))
    assert image_base == IMAGEBASE, 'unexpected ImageBase'
    assert not (dllchars & 0x0040), 'DYNAMIC_BASE set: absolute addresses unsafe'

    # .text must keep raw size == virtual size (tail padding is mapped RX)
    sh_off = opt + optsz
    text_sh = None
    for i in range(nsec):
        s = sh_off + i * 40
        if bytes(d[s:s + 8]).rstrip(b'\x00') == b'.text':
            text_sh = s
            break
    assert text_sh is not None, '.text section not found'
    # section header: +8 VirtualSize, +12 VirtualAddress (RVA),
    #                 +16 SizeOfRawData, +20 PointerToRawData
    vsize, rva, rsize, rptr = struct.unpack_from('<IIII', d, text_sh + 8)
    print('.text   : rva=%#x vsize=%#x rawptr=%#x rsize=%#x'
          % (rva, vsize, rptr, rsize))
    assert (rva, vsize, rptr, rsize) == (
        TEXT_VA - IMAGEBASE, TEXT_RSIZE, TEXT_RAW, TEXT_RSIZE), \
        'unexpected .text layout'

    # ---------------------------------------------------------- current state
    site_off = foff(SITE_VA)
    cur_byte = d[site_off]
    already = cur_byte == SITE_PATCHED
    if not already:
        assert sha == BASE_SHA256, 'unexpected input sha256: %s' % sha
        assert cur_byte == SITE_ORIG, \
            'byte @%#x is %#x, expected %#x' % (SITE_VA, cur_byte, SITE_ORIG)

    ctx = bytes(d[foff(CTX_VA):foff(CTX_VA) + len(CTX_ORIG)])
    print('ctx     :', ctx.hex(' '))
    assert ctx in (CTX_ORIG, CTX_PATCHED), 'context fingerprint mismatch'

    # ------------------------------------------------- fingerprint consistency
    dead = bytes(d[foff(DEAD_VA):foff(DEAD_VA) + len(DEAD_ORIG)])
    assert dead == DEAD_ORIG, 'throw block modified: %s' % dead.hex(' ')

    # ----------------------------------------------------- soundness of patch
    hits = scan_branch_targets(d, DEAD_VA, 0x403AF7)
    print('branch targets into 0x403aeb..0x403af6:', hits or 'none')
    assert not hits, 'throw block is a live branch target: %r' % hits

    # the jump target must be the function's normal continuation
    nxt = SITE_VA + 2
    tgt = nxt + struct.unpack_from('<b', d, site_off + 1)[0]
    print('jcc target: %#x (expected 0x403af7)' % tgt)
    assert tgt == 0x403AF7, 'site no longer branches to 0x403af7'
    assert tgt + 5 <= TEXT_VA + TEXT_RSIZE

    if already:
        print('already patched ->', path)
        return None

    if not write:
        print('DRY-RUN: would patch 1 byte @%#x (file %#x): %#x -> %#x'
              % (SITE_VA, site_off, SITE_ORIG, SITE_PATCHED))
        return None

    # ------------------------------------------------------------------ write
    d[site_off] = SITE_PATCHED
    assert bytes(d[foff(CTX_VA):foff(CTX_VA) + len(CTX_PATCHED)]) == CTX_PATCHED

    d[cksum_off:cksum_off + 4] = struct.pack('<I', 0)
    new_cksum = pe_checksum(bytes(d), cksum_off)
    d[cksum_off:cksum_off + 4] = struct.pack('<I', new_cksum)
    print('checksum: %#x -> %#x' % (checksum, new_cksum))

    # nothing else may have changed
    diff = [i for i, (a, b) in enumerate(zip(cur, d)) if a != b]
    print('changed bytes (%d):' % len(diff), ['%#x' % i for i in diff])
    assert len(diff) <= 5, 'unexpected extra changes'

    os.makedirs(os.path.dirname(BAK), exist_ok=True)
    if not os.path.exists(BAK):
        shutil.copy2(path, BAK)
        print('backup  :', BAK)
    with open(path, 'wb') as fh:
        fh.write(bytes(d))
    out = bytes(d)
    print('WROTE   :', path)
    print('PATCHED_SHA256 =', hashlib.sha256(out).hexdigest())
    print('bytes   :', len(out))
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    flags = {a for a in sys.argv[1:] if a.startswith('-')}
    src = os.path.abspath(args[0]) if args else os.path.abspath(DEFAULT_SRC)
    if '--apply' in flags:
        apply(src, write=True)
    else:
        apply(src, write=False)
        print('(dry-run; pass --apply to write)')
