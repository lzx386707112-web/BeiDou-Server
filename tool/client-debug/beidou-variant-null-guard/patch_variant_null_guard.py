#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BeiDou.exe: _variant_t(IUnknown*) 构造函数的空指针保护。

缺陷
----
    BeiDou.exe+0x410FDF 是一个被 397 处调用的极小叶子函数，语义为
    ATL 的 `_variant_t(IUnknown* pSrc, bool fAddRef = true)`：

        410fdf  cmp  BYTE PTR [esp+0x8],0x0    ; fAddRef
        410fe4  mov  eax,DWORD PTR [esp+0x4]   ; pSrc
        410fe8  push esi
        410fe9  mov  esi,ecx                   ; this
        410feb  mov  WORD PTR [esi],0xd        ; vt = VT_UNKNOWN
        410ff0  mov  DWORD PTR [esi+0x8],eax   ; punkVal = pSrc
        410ff3  je   0x410ffb                  ; fAddRef==0 -> 跳过
        410ff5  mov  ecx,DWORD PTR [eax]       ; <-- pSrc==0 时在此崩溃
        410ff7  push eax
        410ff8  call DWORD PTR [ecx+0x4]       ; AddRef()
        410ffb  mov  eax,esi
        410ffd  pop  esi
        410ffe  ret  8

    只检查了 fAddRef，没有检查 pSrc 是否为 NULL。调用方
    `0x63A858`（地图/UI 刷新路径）在媒体对象获取失败时会传入
    pSrc = NULL、fAddRef = true，于是 `mov ecx,[eax]` 读 0x0 触发
    0xC0000005（崩溃日志：eip=0x410FF5 eax=0 esi=0x1ADA8C）。

做法
----
在 0x410FF5 处（6 字节，0x410FF5..0x410FFA）放一条 `call` 指向
`.text` 尾部空洞 0xAEFE30，桩内先判断 eax 再决定是否 AddRef，最后
`ret` 回到 0x410FFB。`0x410FF3` 的 `je 0x410FFB` 原样保留。

    410ff5  e8 36 ee 6d 00    call 0xAEFE30
    410ffa  90                nop           <- ret 落点
    ...
    aefe30  85 c0             test eax,eax
    aefe32  74 06             je   +6       ; pSrc==0 -> 跳过 AddRef
    aefe34  8b 08             mov  ecx,[eax]
    aefe36  50                push eax
    aefe37  ff 51 04          call [ecx+4]  ; AddRef()
    aefe3a  c3                ret

栈平衡：桩入口 ESP = E-8（call 压入返回地址）；`push eax` 后 E-12，
AddRef 是 stdcall（`ret 4`）回到 E-8；`ret` 回到 E-4，与未打补丁时
AddRef 分支到达 0x410FFB 的 ESP 完全一致。

语义：pSrc != NULL 时逐字节等价；pSrc == NULL 时得到合法的空
VT_UNKNOWN 变体（vt=13, punkVal=0）而不是访问违例。

用法
----
    python3 patch_variant_null_guard.py --dry-run
    python3 patch_variant_null_guard.py --apply
"""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = HERE.parents[2] / "clien" / "BeiDou.exe"

# ---- BeiDou.exe PE 布局（固定 ImageBase 0x400000，无重定位） ----
IMAGE_BASE = 0x400000
TEXT_RVA = 0x1000                           # 节表里存的是 RVA
TEXT_RAW = 0x1000
TEXT_RSIZE = 0x6EF000
TEXT_VA = IMAGE_BASE + TEXT_RVA             # 0x401000
TEXT_END_VA = TEXT_VA + TEXT_RSIZE          # 0xAF0000

# ---- 补丁点 ----
PATCH_VA = 0x410FF5
ORIG_BYTES = bytes.fromhex("8b0850ff5104")  # mov ecx,[eax]; push eax; call [ecx+4]
PATCH_LEN = len(ORIG_BYTES)                 # 6
CONT_VA = 0x410FFB                          # 分支/返回都应落到这里

CAVE_VA = 0xAEFE30
CAVE_BYTES = bytes.fromhex("85c074068b0850ff5104c3")   # 11 字节
# 空洞区之前的最后一个字节（另一处已存在的桩结尾）
CAVE_GUARD_VA = 0xAEFE2E

CALL_INSN_LEN = 5


def va_to_off(va: int) -> int:
    if not (TEXT_VA <= va < TEXT_END_VA):
        raise ValueError("VA %#x 不在 .text 内" % va)
    return va - TEXT_VA + TEXT_RAW

def pe_layout(data: bytes):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise SystemExit("不是 PE 文件")
    machine, nsec = struct.unpack_from("<HH", data, e_lfanew + 4)
    opt_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    image_base = struct.unpack_from("<I", data, opt + 28)[0]
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    checksum_off = opt + 64
    stored = struct.unpack_from("<I", data, checksum_off)[0]
    dllchars = struct.unpack_from("<H", data, opt + 70)[0]
    sec_tab = opt + opt_size
    secs = []
    for i in range(nsec):
        sh = sec_tab + i * 40
        name = bytes(data[sh:sh + 8]).rstrip(b"\0").decode("latin1")
        vsize, vaddr, rsize, rawptr = struct.unpack_from("<IIII", data, sh + 8)
        secs.append((name, vaddr, vsize, rawptr, rsize))
    return dict(machine=machine, nsec=nsec, magic=magic, image_base=image_base,
                size_of_image=size_of_image, checksum_off=checksum_off,
                stored_checksum=stored, dllchar=dllchars, sections=secs)


def pe_checksum(data: bytes, checksum_off: int) -> int:
    d = bytearray(data)
    d[checksum_off:checksum_off + 4] = b"\0\0\0\0"
    total = 0
    n = len(d)
    i = 0
    while i + 1 < n:
        total += d[i] | (d[i + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
        i += 2
    if n % 2:
        total += d[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def build_patch_bytes() -> bytes:
    rel = CAVE_VA - (PATCH_VA + CALL_INSN_LEN)
    if not (-0x80000000 <= rel < 0x80000000):
        raise SystemExit("空洞太远，rel32 放不下")
    return b"\xe8" + struct.pack("<i", rel) + b"\x90" * (PATCH_LEN - CALL_INSN_LEN)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--apply", action="store_true", help="真正写盘（默认只做 dry-run）")
    ap.add_argument("--dry-run", action="store_true", help="只校验不写盘（默认行为）")
    ap.add_argument("--backup", action="store_true",
                    help="写盘前把当前文件复制到 backup/BeiDou.exe.prevpatch")
    args = ap.parse_args()

    src = Path(args.src)
    data = src.read_bytes()
    print("文件        : %s" % src)
    print("大小        : %d" % len(data))
    print("sha256      : %s" % hashlib.sha256(data).hexdigest())

    info = pe_layout(data)
    print("机器        : %#06x  节数=%d  magic=%#06x" %
          (info["machine"], info["nsec"], info["magic"]))
    print("ImageBase   : %#010x  SizeOfImage=%#x  DllCharacteristics=%#06x" %
          (info["image_base"], info["size_of_image"], info["dllchar"]))
    if info["image_base"] != IMAGE_BASE:
        raise SystemExit("ImageBase 与预期不符：%#x" % info["image_base"])
    if info["dllchar"] & 0x40:
        raise SystemExit("出现 DYNAMIC_BASE，绝对地址补丁不安全")
    for name, vaddr, vsize, rawptr, rsize in info["sections"]:
        if name == ".text":
            print(".text       : rva=%#x vsize=%#x raw=%#x rsize=%#x" %
                  (vaddr, vsize, rawptr, rsize))
            if (vaddr, vsize, rawptr, rsize) != (TEXT_RVA, TEXT_RSIZE, TEXT_RAW, TEXT_RSIZE):
                raise SystemExit("未预期的 .text 布局")

    # 自检：校验和算法必须能复现文件里已有的值
    calc = pe_checksum(data, info["checksum_off"])
    print("CheckSum    : 文件=%#010x  重算=%#010x  %s" %
          (info["stored_checksum"], calc,
           "OK" if calc == info["stored_checksum"] else "不一致!"))
    if calc != info["stored_checksum"]:
        raise SystemExit("PE CheckSum 自检失败，拒绝继续")

    patch = build_patch_bytes()
    off = va_to_off(PATCH_VA)
    cave_off = va_to_off(CAVE_VA)
    cur = bytes(data[off:off + PATCH_LEN])
    cave_cur = bytes(data[cave_off:cave_off + len(CAVE_BYTES)])
    tail_cur = bytes(data[va_to_off(CAVE_VA):va_to_off(TEXT_END_VA - 1) + 1])

    print()
    print("补丁点 %#x (文件偏移 %#x)" % (PATCH_VA, off))
    print("  当前  : %s" % cur.hex(" "))
    print("  改写为: %s" % patch.hex(" "))
    print("空洞 %#x (文件偏移 %#x)" % (CAVE_VA, cave_off))
    print("  当前  : %s" % cave_cur.hex(" "))
    print("  写入为: %s" % CAVE_BYTES.hex(" "))
    print("空洞前一个字节 %#x = %02x（另一处既有桩的结尾，必须不变）" %
          (CAVE_GUARD_VA, data[va_to_off(CAVE_GUARD_VA)]))

    if cur == patch and cave_cur == CAVE_BYTES:
        print()
        print("status: already patched")
        print("sha256: %s" % hashlib.sha256(data).hexdigest())
        return 0
    if cur != ORIG_BYTES:
        raise SystemExit("补丁点字节与基线不符（%s），拒绝改写" % cur.hex(" "))
    if cave_cur != b"\0" * len(CAVE_BYTES):
        raise SystemExit("空洞区非零，拒绝复用")
    if any(tail_cur):
        nz = [CAVE_VA + i for i, b in enumerate(tail_cur) if b][:8]
        raise SystemExit("空洞区并非全零，非零起点 %s" %
                         [hex(v) for v in nz])

    out = bytearray(data)
    out[off:off + PATCH_LEN] = patch
    out[cave_off:cave_off + len(CAVE_BYTES)] = CAVE_BYTES
    new_cks = pe_checksum(bytes(out), info["checksum_off"])
    struct.pack_into("<I", out, info["checksum_off"], new_cks)
    print("CheckSum    : %#010x -> %#010x" % (info["stored_checksum"], new_cks))

    diff = [i for i in range(len(out)) if out[i] != data[i]]
    print("变化字节    : %d 处  %s" % (len(diff), [hex(i) for i in diff]))

    if not args.apply:
        print()
        print("status: dry-run（未写盘）")
        return 0

    if args.backup:
        bdir = HERE / "backup"
        bdir.mkdir(parents=True, exist_ok=True)
        bpath = bdir / "BeiDou.exe.prevpatch"
        if not bpath.exists():
            bpath.write_bytes(data)
            print("备份        : %s" % bpath)
    src.write_bytes(bytes(out))
    final = src.read_bytes()
    print()
    print("status: applied")
    print("sha256: %s" % hashlib.sha256(final).hexdigest())
    print("PATCHED_SHA256=%s" % hashlib.sha256(final).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
