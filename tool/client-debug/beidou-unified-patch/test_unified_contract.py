#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BeiDou.exe 统一补丁契约测试

判定标准不是"字节看起来对"，而是**控制流事实**：
  * 基线里 0x403AF2 的 _com_raise_error 调用**可达** -> 补丁后**不可达**
  * 基线里四处缺陷指令**可达** -> 补丁后都变成受保护桩
  * 全 .text 没有任何分支进入被替换字节区间
  * 禁改区（加载器 thunk / 既有桩）逐字节不变

需要 capstone：只有 /opt/homebrew/bin/python3 有。
"""

from __future__ import annotations

import hashlib
import os
import struct
import sys

try:
    import capstone
except ImportError:
    sys.stderr.write("需要 capstone：请用 /opt/homebrew/bin/python3 运行\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
TARGET = os.path.join(REPO, "clien", "BeiDou.exe")
BASELINE = os.path.join(HERE, "backup", "BeiDou.exe.orig")

IMAGE_BASE = 0x400000
TEXT_VA = 0x401000
TEXT_RAW = 0x1000
TEXT_RSIZE = 0x6EF000
TEXT_END_VA = TEXT_VA + TEXT_RSIZE

BASELINE_SHA256 = "06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18"
BASELINE_CHECKSUM = 0x004213DC

FUNC_A_LO, FUNC_A_HI = 0x403A93, 0x403B27     # 含 _com_error 抛出的函数
THROW_SITE = 0x403AF2                          # call 0xa5fdf2
DEAD_LO, DEAD_HI = 0x403AEB, 0x403AF7          # 补丁后应不可达的抛出序言

CAVE_A, CAVE_B, CAVE_C = 0xAEFE30, 0xAEFE40, 0xAEFE60
CAVE_D = 0xAEFE80
CAVE_E = 0xAEFEA0
CAVE_F = 0xAEFEB0
CAVE_G = 0xAEFEE0

# P5：属性取址器（E_POINTER）家族
GETTER = 0x40263B               # 共享取址器：空则抛 _com_error(E_POINTER)
GETITEM_WRAPPER = 0x403935      # get_item 包装 0x403935（119 个站点喂给它）
GETITEM_GUARD_SITE = 0x403965   # get_item 包装 0x403935 里无判空的 `mov ecx,[esi]`
GETITEM_RESUME = 0x40396A       # 桩 D 非空时回原流程
GETITEM_EMPTY = 0x403980        # 桩 D 空值时直接出空结果
FUNC_P5_LO = 0x5CAC3D           # 09-28 崩溃所在函数的入口（含 SEH prologue）
FUNC_P5_RET = 0x5CF58C          # 该函数唯一出口 `ret 0xc`

WRAP_1C = 0x4039F1              # this->vtbl[7](&out)，ret 4
WRAP_1C_SITE = 0x4039F5
WRAP_1C_RESUME = 0x4039FC
WRAP_1C_OLD = bytes.fromhex("83 65 fc 00 56 8b f1")
WRAP_20 = 0x409EEF              # this->vtbl[8]() -> DWORD，ret
WRAP_20_SITE = 0x409EF6
WRAP_20_RESUME = 0x409EFC
WRAP_20_OLD = bytes.fromhex("8b 06 8d 4d fc 51")

P5_GETTER_SITES = [
    0x5CADAC, 0x5CAE2D, 0x5CAE9D, 0x5CAF20, 0x5CAF94,
    0x5CAFFE, 0x5CB09F, 0x5CB112, 0x5CB183, 0x5CB1F4,
    0x5CB265, 0x5CB2D6, 0x5CB347, 0x5CB3B8, 0x5CB42B,
    0x5CB49F, 0x5CB518, 0x5CB58F, 0x5CB606, 0x5CB67D,
    0x5CB6F4, 0x5CB76B, 0x5CB7E2, 0x5CB859, 0x5CB8D0,
    0x5CB947, 0x5CB9BE, 0x5CBA35, 0x5CBAAC, 0x5CBB23,
    0x5CBB9A, 0x5CBC11, 0x5CBC88, 0x5CBCFF, 0x5CBD76,
    0x5CBDED, 0x5CBE55, 0x5CBEBD, 0x5CBF25, 0x5CBF8D,
    0x5CBFF5, 0x5CC05D, 0x5CC0C5, 0x5CC12D, 0x5CC195,
    0x5CC212, 0x5CC29D, 0x5CC323, 0x5CC39A, 0x5CC402,
    0x5CC47A, 0x5CC4D4, 0x5CC53D, 0x5CC5A6, 0x5CC60F,
    0x5CC66C, 0x5CC6C1, 0x5CC71C, 0x5CC789, 0x5CC7DD,
    0x5CC841, 0x5CC89D, 0x5CC8F9, 0x5CCC39, 0x5CCC95,
    0x5CCD0C, 0x5CCD75, 0x5CCDC2, 0x5CCE37, 0x5CCF70,
    0x5CD166, 0x5CD391, 0x5CD3F2, 0x5CD453, 0x5CD4B4,
    0x5CD515, 0x5CD576, 0x5CD5D7, 0x5CD638, 0x5CD699,
    0x5CD6F5, 0x5CD759, 0x5CD8F4, 0x5CD966, 0x5CD9C5,
    0x5CDA06, 0x5CDA84, 0x5CDAE1, 0x5CDB20, 0x5CDBAE,
    0x5CDC05, 0x5CDC52, 0x5CDD32, 0x5CDD7F, 0x5CDE72,
    0x5CDEBF, 0x5CDFB2, 0x5CDFFF, 0x5CE0DF, 0x5CE12C,
    0x5CE20C, 0x5CE259, 0x5CE34C, 0x5CE399, 0x5CE48C,
    0x5CE4D9, 0x5CE5D3, 0x5CE624, 0x5CE71D, 0x5CE76E,
    0x5CE867, 0x5CE8B8, 0x5CE9B1, 0x5CEA02, 0x5CEAFB,
    0x5CEB4C, 0x5CEC45, 0x5CEC96, 0x5CED8F, 0x5CEDE0,
    0x5CEF09, 0x5CEF71, 0x5CEFE8, 0x5CF090, 0x5CF242,
    0x5CF406, 0x5CF47D,
]

COMBINED_LO, COMBINED_HI = 0x401D3E, 0x401D58  # 两处 WZ 补丁的合并区间
FORBIDDEN = [(0xAEFA20, 0xAEFA40), (0xAEFD80, 0xAEFE00)]

FAILS = []


def check(cond, msg):
    print("  [%s] %s" % ("OK " if cond else "FAIL", msg))
    if not cond:
        FAILS.append(msg)
    return cond


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def pe_checksum(data: bytes) -> int:
    e = struct.unpack_from("<I", data, 0x3C)[0]
    cks_off = e + 24 + 64
    total, n = 0, len(data)
    for i in range(0, n - (n % 2), 2):
        if cks_off <= i < cks_off + 4:
            continue
        total += struct.unpack_from("<H", data, i)[0]
        total = (total & 0xFFFF) + (total >> 16)
    if n % 2:
        total += data[-1]
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def pe_checksum_field(d):
    e = struct.unpack_from("<I", d, 0x3C)[0]
    return struct.unpack_from("<I", d, e + 24 + 64)[0], e + 24 + 64


def mkbuf(d):
    return bytes(d[TEXT_RAW:TEXT_RAW + TEXT_RSIZE])


def fo(va):
    """.text 节内偏移（cb/cc 都是 mkbuf() 出来的 .text 切片，不是整文件）。"""
    return va - TEXT_VA


MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)


def dis1(code, base, va):
    off = va - base
    if off < 0 or off + 1 > len(code):
        return None
    return next(MD.disasm(bytes(code[off:off + 16]), va), None)


def target_of(ins):
    try:
        return int(ins.op_str, 16)
    except ValueError:
        return None


def jmp_to(at_va, dst_va):
    """在 at_va 处的 `E9 rel32` 字节。"""
    return b"\xE9" + struct.pack("<i", dst_va - (at_va + 5))


def next_call_target(code, base, va, limit=12):
    """从 va 起顺序看至多 limit 条指令，返回第一个 call 的目标。

    遇到 jcc / jmp / ret 就放弃（返回 None）——那些站点不是"紧跟一个包装调用"
    的形状，不能按统一规则处理。
    """
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    off = va - base
    for _ in range(limit):
        ins = next(md.disasm(bytes(code[off:off + 16]), va), None)
        if ins is None:
            return None
        if ins.mnemonic == "call":
            return target_of(ins)
        if ins.mnemonic.startswith("j") or ins.mnemonic.startswith("ret"):
            return None
        off += ins.size
        va += ins.size
    return None


def feeds_eax_to_ecx(code, base, va, limit=12):
    """站点之后、第一个 call 之前，是否出现 `mov ecx,eax`（把返回值当 this 用）。"""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    off = va - base
    for _ in range(limit):
        ins = next(md.disasm(bytes(code[off:off + 16]), va), None)
        if ins is None:
            return False
        if ins.mnemonic == "call":
            return False
        if ins.mnemonic == "mov" and ins.op_str.replace(" ", "") == "ecx,eax":
            return True
        off += ins.size
        va += ins.size
    return False


def walk(code, base, entry, max_insns=300000):
    """从 entry 做 CFG 遍历；call 视为顺序执行（只看本函数体内可达性）。"""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    visited = {}
    pending = [entry]
    guard = 0
    while pending:
        va = pending.pop()
        while va not in visited:
            guard += 1
            if guard > max_insns:
                return visited
            off = va - base
            if off < 0 or off + 1 > len(code):
                break
            ins = next(md.disasm(bytes(code[off:off + 16]), va), None)
            if ins is None:
                break
            visited[va] = ins
            mn = ins.mnemonic
            if mn.startswith("ret") or mn in ("hlt", "int3", "ud2"):
                break
            if mn == "jmp":
                t = target_of(ins)
                if t is None:
                    break
                va = t
                continue
            if mn.startswith("j") and mn != "jmp":
                t = target_of(ins)
                if t is not None:
                    pending.append(t)
                va = ins.address + ins.size
                continue
            va = ins.address + ins.size
    return visited


def main():
    base = open(BASELINE, "rb").read()
    cur = open(TARGET, "rb").read()
    cb, cc = mkbuf(base), mkbuf(cur)

    print("=" * 74)
    print("1. 基线与补丁版文件级校验")
    print("=" * 74)
    check(sha256(base) == BASELINE_SHA256, "基线 sha256 = %s" % BASELINE_SHA256[:16])
    bc, _ = pe_checksum_field(base)
    check(bc == BASELINE_CHECKSUM,
          "基线 PE CheckSum = %#010x（= 崩溃转储里记录的 %#010x）" % (bc, BASELINE_CHECKSUM))
    check(len(base) == len(cur), "补丁后文件大小不变（%d 字节）" % len(cur))
    pc, poff = pe_checksum_field(cur)
    check(pc == pe_checksum(cur), "补丁版 PE CheckSum 字段(%#010x) 与复算一致" % pc)
    check(pc != bc, "补丁版 CheckSum 已刷新（%#010x != %#010x）" % (pc, bc))

    print()
    print("=" * 74)
    print("2. 基线：四处缺陷都真实存在且可达")
    print("=" * 74)

    b_a = walk(cb, TEXT_VA, FUNC_A_LO, max_insns=20000)
    check(THROW_SITE in b_a, "基线 F_A 内 %#x(call _com_raise_error) 可达" % THROW_SITE)
    check(DEAD_LO in b_a, "基线 %#x..%#x 抛出序言可达" % (DEAD_LO, DEAD_HI))
    check(cb[fo(0x403AE9)] == 0x7D,
          "基线 %#x = %#x (`jge +0xc`)" % (0x403AE9, cb[fo(0x403AE9)]))

    fn_v = walk(cb, TEXT_VA, 0x410FDF, max_insns=20000)
    check(0x410FF5 in fn_v, "基线 %#x(_variant_t 空指针解引用) 可达" % 0x410FF5)
    check(cb[fo(0x410FF5):fo(0x410FF5) + 6] == bytes.fromhex("8b 08 50 ff 51 04"),
          "基线 %#x 是 `mov ecx,[eax]; push eax; call [ecx+4]`" % 0x410FF5)

    fn_w = walk(cb, TEXT_VA, 0x401C74, max_insns=40000)
    check(0x401D3E in fn_w, "基线 %#x(WZ 链首解引用) 可达" % 0x401D3E)
    check(0x401D52 in fn_w, "基线 %#x(WZ 数组解引用/本次崩溃点) 可达" % 0x401D52)
    check(0x401D4E in fn_w and cb[fo(0x401D4E):fo(0x401D4E) + 2] == bytes.fromhex("33 c0"),
          "基线 %#x 是 `xor eax,eax`（把 eax 置 0 后仍被解引用 -> 崩溃根因）" % 0x401D4E)

    all_zero = all(cb[fo(v)] == 0 for v in range(CAVE_A, CAVE_D + 0x20))
    check(all_zero, "基线 %#x..%#x 代码空洞全零（可放桩）" % (CAVE_A, CAVE_D + 0x20))

    print()
    print("=" * 74)
    print("3. 补丁版：COM 抛出点已不可达")
    print("=" * 74)
    check(cc[fo(0x403AE9)] == 0xEB, "%#x = 0xeb (`jmp +0xc`)" % 0x403AE9)
    c_a = walk(cc, TEXT_VA, FUNC_A_LO, max_insns=20000)
    check(THROW_SITE not in c_a,
          "补丁后 %#x(call _com_raise_error) 从 F_A 入口**不可达**" % THROW_SITE)
    dead = [v for v in range(DEAD_LO, DEAD_HI) if v in c_a]
    check(not dead, "补丁后 %#x..%#x 整段不可达" % (DEAD_LO, DEAD_HI))
    check(0x403AF7 in c_a, "补丁后落到正常收尾 %#x（mov ecx,[ebp+0x8]）" % 0x403AF7)
    check(cc[fo(0x403AF7):fo(0x403AF7) + 3] == bytes.fromhex("8b 4d 08"),
          "基线/补丁版 %#x 起都是 `mov ecx,[ebp+0x8]`（未被改动）" % 0x403AF7)
    check(cb[fo(0x403AEB):fo(0x403AF7)] == cc[fo(0x403AEB):fo(0x403AF7)],
          "被跳过的抛出序言字节逐字节保留（便于比对/回退）")

    print()
    print("=" * 74)
    print("4. 补丁版：三处代码桩的语义")
    print("=" * 74)

    # --- 桩 A
    cave_a = cc[fo(CAVE_A):fo(CAVE_A) + 11]
    ins = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(cave_a, CAVE_A))
    print("    桩A @%#x: %s" % (CAVE_A, "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins)))
    check(ins[0].mnemonic == "test" and ins[0].op_str.replace(" ", "") == "eax,eax",
          "桩A 首条 `test eax,eax`")
    check(ins[1].mnemonic == "je" and target_of(ins[1]) == CAVE_A + 10,
          "桩A `je %#x`（为空直接 ret）" % (CAVE_A + 10))
    check(ins[2].mnemonic == "mov" and ins[2].op_str.replace(" ", "") == "ecx,dwordptr[eax]",
          "桩A 保留 `mov ecx,[eax]`")
    check(ins[3].mnemonic == "push" and ins[3].op_str == "eax", "桩A 保留 `push eax`")
    check(ins[4].mnemonic == "call" and ins[4].op_str.replace(" ", "") == "dwordptr[ecx+4]",
          "桩A 保留 `call [ecx+4]`（AddRef，被调方 ret 4 清栈）")
    check(ins[5].mnemonic == "ret", "桩A 以 ret 收尾（栈平衡与基线 `je` 跳过路径一致）")

    p2 = cc[fo(0x410FF5):fo(0x410FF5) + 6]
    i2 = next(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(p2, 0x410FF5))
    check(i2.mnemonic == "call" and target_of(i2) == CAVE_A,
          "%#x 变成 `call %#x`(桩A)" % (0x410FF5, CAVE_A))
    check(p2[5] == 0x90, "%#x 尾字节为 nop（凑满原 6 字节）" % (0x410FF5 + 5))

    # --- 桩 B
    cave_b = cc[fo(CAVE_B):fo(CAVE_B) + 23]
    ins = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(cave_b, CAVE_B))
    print("    桩B @%#x: %s" % (CAVE_B, "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins)))
    check(ins[0].mnemonic == "test" and ins[0].op_str.replace(" ", "") == "edi,edi",
          "桩B 首条 `test edi,edi`（补上缺失的判空）")
    check(ins[1].mnemonic == "je" and target_of(ins[1]) == CAVE_B + 0x12,
          "桩B `je %#x`（edi==0 跳到桩尾）" % (CAVE_B + 0x12))
    check(ins[2].mnemonic == "mov" and ins[2].op_str.replace(" ", "") == "ax,wordptr[edi]",
          "桩B 保留 `mov ax,[edi]`（非空路径逐字节等价）")
    check(ins[3].mnemonic == "test" and ins[3].op_str.replace(" ", "") == "ax,ax",
          "桩B 保留 `test ax,ax` 并设置 ZF")
    check(ins[4].mnemonic == "jmp" and target_of(ins[4]) == 0x401D58,
          "桩B 非空时 `jmp %#x`（回原流程，jmp 不改 ZF，原 je 仍有效）" % 0x401D58)
    check(ins[-1].mnemonic == "jmp" and target_of(ins[-1]) == 0x401D11,
          "桩B 为空时 `jmp %#x`（= 基线中 `*edi==0` 的既有出口，外层循环头）" % 0x401D11)

    p4 = cc[fo(0x401D52):fo(0x401D52) + 6]
    i4 = next(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(p4, 0x401D52))
    check(i4.mnemonic == "jmp" and target_of(i4) == CAVE_B,
          "%#x 变成 `jmp %#x`(桩B)" % (0x401D52, CAVE_B))
    check(p4[5] == 0x90, "%#x 尾字节为 nop" % (0x401D57))
    check(cc[fo(0x401D50):fo(0x401D50) + 2] == bytes.fromhex("8b f8"),
          "%#x 的 `mov edi,eax` 未被改动（桩B 依赖它）" % 0x401D50)
    check(cc[fo(0x401D58):fo(0x401D58) + 2] == bytes.fromhex("74 b7"),
          "%#x 的 `je %#x` 未被改动（仍是活分支）" % (0x401D58, 0x401D11))

    # --- 桩 C
    cave_c = cc[fo(CAVE_C):fo(CAVE_C) + 24]
    ins = list(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(cave_c, CAVE_C))
    print("    桩C @%#x: %s" % (CAVE_C, "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins)))
    seq = [(i.mnemonic, i.op_str.replace(" ", "")) for i in ins]
    check(seq[0] == ("xor", "eax,eax"), "桩C 先 `xor eax,eax`（默认置空）")
    check(seq[1] == ("test", "esi,esi"), "桩C 判 `esi`")
    check(ins[2].mnemonic == "je" and target_of(ins[2]) == CAVE_C + 0x13,
          "桩C `je %#x`（esi 为空 -> 走置空路径）" % (CAVE_C + 0x13))
    check(seq[3] == ("mov", "eax,dwordptr[esi+0x20]"), "桩C 保留 `mov eax,[esi+0x20]`")
    check(seq[4] == ("test", "eax,eax"), "桩C 判 `esi->[0x20]`")
    check(ins[5].mnemonic == "je" and target_of(ins[5]) == CAVE_C + 0x13,
          "桩C 第二处 `je %#x`" % (CAVE_C + 0x13))
    check(seq[6] == ("mov", "eax,dwordptr[eax+0x14]"), "桩C 保留 `mov eax,[eax+0x14]`")
    check(ins[-1].mnemonic == "jmp" and target_of(ins[-1]) == 0x401D44,
          "桩C 回到 %#x（test eax,eax）——**不跳过** 0x401D46 的 `mov ebx,edx`" % 0x401D44)
    check(cc[fo(0x401D44):fo(0x401D44) + 4] == bytes.fromhex("85 c0 8b da"),
          "%#x 的 `test eax,eax; mov ebx,edx` 未被改动" % 0x401D44)

    p3 = cc[fo(0x401D3E):fo(0x401D3E) + 6]
    i3 = next(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(p3, 0x401D3E))
    check(i3.mnemonic == "jmp" and target_of(i3) == CAVE_C,
          "%#x 变成 `jmp %#x`(桩C)，只替换 6 字节" % (0x401D3E, CAVE_C))
    check(p3[5:] == b"\x90", "%#x 尾字节 nop（0x401D44 的 test 保留给桩C 设置 ZF）" % 0x401D43)

    print()
    print("=" * 74)
    print("4b. 补丁版：桩 D 与 P5（属性取址器 E_POINTER 家族）")
    print("=" * 74)

    # ---- 基线事实 1：共享取址器 0x40263B 是"空则抛 E_POINTER"
    check(cb[fo(0x40263B):fo(0x40263B) + 14] == bytes.fromhex(
        "56 8b f1 83 3e 00 75 0a 68 03 40 00 80 e8"),
        "基线 %#x 是 `push esi; mov esi,ecx; cmpl $0,(%%esi); jne; push $0x80004003; "
        "call _com_issue_error`" % 0x40263B)
    check(cc[fo(0x40263B):fo(0x40263B) + 15] == cb[fo(0x40263B):fo(0x40263B) + 15],
          "**共享取址器 %#x 逐字节未改动**（2406 个调用点把返回值当 this 用，"
          "改成返回 0 会变成 0 地址解引用）" % 0x40263B)

    # ---- 基线事实 2：E_POINTER 全局只被"产生"，从不被"处理"
    md0 = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    ep_prod = ep_cmp = ni_prod = ni_cmp = 0
    va0 = TEXT_VA
    while va0 < TEXT_VA + TEXT_RSIZE:
        i0 = next(md0.disasm(bytes(cb[fo(va0):fo(va0) + 16]), va0), None)
        if i0 is None:
            va0 += 1
            continue
        if "0x80004003" in i0.op_str:
            if i0.mnemonic == "cmp":
                ep_cmp += 1
            else:
                ep_prod += 1
        if "0x80004002" in i0.op_str:
            if i0.mnemonic == "cmp":
                ni_cmp += 1
            else:
                ni_prod += 1
        va0 += i0.size
    check(ep_cmp == 0 and ep_prod > 4000,
          "全 .text 中 E_POINTER(0x80004003)：%d 处产生 / **%d 处比较** —— "
          "无人处理，抛出去只能是致命错误" % (ep_prod, ep_cmp))
    check(ni_cmp > 1000,
          "全 .text 中 E_NOINTERFACE(0x80004002)：%d 处比较 —— 这才是客户端设计上"
          "『接口不可用』的降级信号（崩溃函数自己在 0x5CAD25 就这么用）" % ni_cmp)

    # ---- 基线事实 3：崩溃函数内 127 个取址器调用点，按消费者分三组
    base_fn = walk(cb, TEXT_VA, FUNC_P5_LO, max_insns=400000)
    base_calls = sorted(a for a, i in base_fn.items()
                        if i.mnemonic == "call" and target_of(i) == GETTER)
    check(len(base_calls) == len(P5_GETTER_SITES) == 127,
          "基线 %#x 函数体内对 %#x 的调用点 = %d 个（期望 %d）"
          % (FUNC_P5_LO, GETTER, len(base_calls), len(P5_GETTER_SITES)))
    check(base_calls == sorted(P5_GETTER_SITES),
          "调用点集合与 P5_GETTER_SITES 完全一致")
    check(cb[fo(FUNC_P5_RET):fo(FUNC_P5_RET) + 3] == bytes.fromhex("c2 0c 00"),
          "%#x 函数唯一出口是 `ret 0xc`（19 KB、单出口，边界可界定）" % FUNC_P5_RET)

    groups = {}
    for a in base_calls:
        groups.setdefault(next_call_target(cb, TEXT_VA, a + 5), []).append(a)
    check(sorted(groups) == sorted([GETITEM_WRAPPER, WRAP_1C, WRAP_20]),
          "127 个站点的消费者恰好是 %#x / %#x / %#x 三选一"
          % (GETITEM_WRAPPER, WRAP_1C, WRAP_20))
    check(len(groups.get(GETITEM_WRAPPER, [])) == 119,
          "%#x(get_item wrapper) 消费 %d 个站点（期望 119）"
          % (GETITEM_WRAPPER, len(groups.get(GETITEM_WRAPPER, []))))
    check(len(groups.get(WRAP_1C, [])) == 6,
          "%#x(vtbl[7], ret 4) 消费 %d 个站点（期望 6）" % (WRAP_1C, len(groups.get(WRAP_1C, []))))
    check(len(groups.get(WRAP_20, [])) == 2,
          "%#x(vtbl[8], ret) 消费 %d 个站点（期望 2）" % (WRAP_20, len(groups.get(WRAP_20, []))))
    bad_shape = []
    for a in base_calls:
        o = fo(a)
        if cb[o] != 0xE8:
            bad_shape.append((a, "不是 call rel32"))
            continue
        if (a + 5 + struct.unpack_from("<i", cb, o + 1)[0]) & 0xFFFFFFFF != GETTER:
            bad_shape.append((a, "目标不是取址器"))
        if not feeds_eax_to_ecx(cb, TEXT_VA, a + 5):
            bad_shape.append((a, "返回值未被喂给 ecx"))
    check(not bad_shape,
          "127 个站点都是 `call 取址器` 且返回值经 `mov ecx,eax` 当 this 用（%d 个异形）"
          % len(bad_shape))

    check(0x5CADAC in base_fn,
          "基线 %#x（崩溃点：取用空的 IWzProperty 缓存槽）可达" % 0x5CADAC)
    check(cb[fo(0x5CADAC):fo(0x5CADAC) + 5] == bytes.fromhex("e8 8a 78 e3 ff"),
          "基线 %#x = `call %#x`（日志 stack_candidates 里的 s52=0x5CADB1 就是它的返回点）"
          % (0x5CADAC, GETTER))
    check(cb[fo(0x5CADAC) - 7:fo(0x5CADAC) - 4] == bytes.fromhex("8d 4d 9c"),
          "基线 %#x 前是 `lea -0x64(%%ebp),%%ecx`（槽位与转储证据一致）" % 0x5CADAC)
    check(next_call_target(cb, TEXT_VA, 0x5CADAC + 5) == GETITEM_WRAPPER,
          "基线 %#x 的返回值喂给 %#x（与 dump_inspect rets 的调用链一致）"
          % (0x5CADAC, GETITEM_WRAPPER))
    # 崩溃前一步 0x5CAD0B `cmp eax,ebx` / 0x5CAD10 把槽清 0 / 0x5CAD13 在源对象为空时
    # 跳过 QI，而 0x5CAD25 已经用 E_NOINTERFACE 标记"接口不可用"
    # => 空槽本就是设计内的状态，后面的取址器抛 E_POINTER 才是自相矛盾。
    check(cb[fo(0x5CAD0B):fo(0x5CAD0B) + 10] ==
          bytes.fromhex("3b c3 89 45 98 89 5d 9c 74 21"),
          "基线 %#x 起 `cmp eax,ebx / mov [ebp-0x68],eax / mov [ebp-0x64],ebx / je +0x21`"
          "（槽先清 0，源对象为空则跳过 QI）" % 0x5CAD0B)
    check(cb[fo(0x5CAD25):fo(0x5CAD25) + 5] == bytes.fromhex("bb 02 40 00 80"),
          "基线 %#x 处 `mov ebx,0x80004002`(E_NOINTERFACE) —— "
          "空接口是已知并容忍的状态" % 0x5CAD25)

    # ---- 补丁事实
    def cave_bytes(va, n):
        return cc[fo(va):fo(va) + n]

    # 桩 D（P5a）
    ins_d = list(md0.disasm(cave_bytes(CAVE_D, 20), CAVE_D))
    print("    桩D @%#x: %s" % (CAVE_D, "; ".join("%s %s" % (i.mnemonic, i.op_str) for i in ins_d)))
    exp_d = (b"\x85\xF6" + b"\x74\x0B" + b"\x8B\x0E" + b"\x8D\x55\xE0"
             + jmp_to(CAVE_D + 9, GETITEM_RESUME) + b"\x90"
             + jmp_to(CAVE_D + 15, GETITEM_EMPTY))
    check(cave_bytes(CAVE_D, len(exp_d)) == exp_d,
          "桩D 逐字节符合设计：`test esi,esi` -> `je +0x0B` / 保留 `mov ecx,[esi]; "
          "lea edx,-0x20(%%ebp)` / 非空 jmp %#x / 空 jmp %#x" % (GETITEM_RESUME, GETITEM_EMPTY))
    check(ins_d[1].mnemonic == "je" and target_of(ins_d[1]) == CAVE_D + 15,
          "桩D `je %#x`（this==0 -> 出空结果）" % (CAVE_D + 15))
    check(cc[fo(GETITEM_EMPTY):fo(GETITEM_EMPTY) + 9] ==
          cb[fo(GETITEM_EMPTY):fo(GETITEM_EMPTY) + 9],
          "%#x 起的『拷贝空 VARIANT -> 释放 -> 返回出参』序列未被改动" % GETITEM_EMPTY)
    check(cc[fo(GETITEM_RESUME):fo(GETITEM_RESUME) + 11] ==
          cb[fo(GETITEM_RESUME):fo(GETITEM_RESUME) + 11],
          "%#x 起的 push edx / push eax / push esi / call [ecx+0x14] 未被改动" % GETITEM_RESUME)
    i5a = next(md0.disasm(cc[fo(GETITEM_GUARD_SITE):fo(GETITEM_GUARD_SITE) + 5],
                          GETITEM_GUARD_SITE))
    check(i5a.mnemonic == "jmp" and target_of(i5a) == CAVE_D,
          "%#x 变成 `jmp %#x`(桩D)，只替换 5 字节" % (GETITEM_GUARD_SITE, CAVE_D))
    check(cb[fo(GETITEM_GUARD_SITE):fo(GETITEM_GUARD_SITE) + 5] == bytes.fromhex("8b 0e 8d 55 e0"),
          "基线 %#x = `mov ecx,[esi]; lea edx,[ebp-0x20]`（正好 5 字节，被桩D 逐字节等价复刻）"
          % GETITEM_GUARD_SITE)
    # 0x403980 之后以 `leave` 收尾（leave 重置 esp），所以桩D 直接落过去是安全的
    check(cc[fo(0x4039A8):fo(0x4039A8) + 4] == bytes.fromhex("c9 c2 08 00"),
          "%#x 处 `leave; ret 8` 未变（leave 会重置 esp，桩D 的空分支栈深度因此安全）"
          % 0x4039A8)

    # 桩 E（P5b）：取址器的容错克隆
    exp_e = bytes.fromhex("8b 01 c3")
    check(cave_bytes(CAVE_E, 3) == exp_e,
          "桩E = `mov eax,[ecx]; ret` —— 与 %#x 的非抛异常路径等价，且完全不碰 esi" % GETTER)
    ins_e = list(md0.disasm(exp_e, CAVE_E))
    check(ins_e[0].mnemonic == "mov" and ins_e[0].op_str.replace(" ", "") == "eax,dwordptr[ecx]"
          and ins_e[1].mnemonic == "ret",
          "桩E 反汇编为 `mov eax,dword ptr [ecx]` + `ret`（无 push/je）")
    check(b"\x68" not in exp_e and b"\xe8" not in exp_e,
          "桩E 里不存在 push 立即数（0x80004003）/ 调用 _com_issue_error")

    bad_tol = []
    for a in P5_GETTER_SITES:
        o = fo(a)
        seg = cc[o:o + 5]
        i = next(md0.disasm(seg, a), None)
        if i is None or i.mnemonic != "call" or target_of(i) != CAVE_E:
            bad_tol.append((a, seg.hex(" ")))
            continue
        if seg[0] != 0xE8:
            bad_tol.append((a, "不是 E8"))
        if cc[o - 8:o] != cb[o - 8:o] or cc[o + 5:o + 13] != cb[o + 5:o + 13]:
            bad_tol.append((a, "调用点前后字节被改动（超出了 5 字节操作数窗口）"))
    check(not bad_tol,
          "127 处取址器调用已全部原地改指桩E（只改 E8 的 rel32 操作数，前后字节未动）%s"
          % (bad_tol[:4] or ""))

    cur_fn = walk(cc, TEXT_VA, FUNC_P5_LO, max_insns=400000)
    cur_calls = [a for a, i in cur_fn.items()
                 if i.mnemonic == "call" and target_of(i) == GETTER]
    check(not cur_calls,
          "补丁后 %#x 函数体内对 %#x 的调用点 = 0（抛点已全部消除）" % (FUNC_P5_LO, GETTER))
    cur_tol = sorted(a for a, i in cur_fn.items()
                     if i.mnemonic == "call" and target_of(i) == CAVE_E)
    check(cur_tol == sorted(P5_GETTER_SITES),
          "补丁后 %#x 函数体内调用桩E 的站点恰好 %d 个，无多无少"
          % (FUNC_P5_LO, len(cur_tol)))
    check(cc[fo(0x5CADA5):fo(0x5CADA5) + 3] == bytes.fromhex("8d 4d 9c"),
          "%#x 的 `lea -0x64(%%ebp),%%ecx` 保留（改目标不再依赖它传 this，但字节未动）"
          % 0x5CADA5)

    # 桩 F（P5c）：0x4039F1 的 this 判空
    exp_f = (bytes.fromhex("83 65 fc 00 56 8b f1 85 c9 74 0b 8b 06")
             + jmp_to(CAVE_F + 13, WRAP_1C_RESUME)
             + b"\x90\x90\x90\x90"
             + bytes.fromhex("8b 45 08 8b 4d fc 89 08 5e c9 c2 04 00"))
    check(cave_bytes(CAVE_F, len(exp_f)) == exp_f,
          "桩F 逐字节符合设计：补做 `and [ebp-4],0 / push esi / mov esi,ecx`，"
          "`test ecx,ecx` -> `je +0x0B`；空分支把 [ebp-4](=0) 写进 `*[ebp+8]` 后 "
          "`pop esi / leave / ret 4`")
    ins_f = list(md0.disasm(exp_f, CAVE_F))
    check(ins_f[4].mnemonic == "je" and target_of(ins_f[4]) == CAVE_F + 22,
          "桩F `je %#x`（this==0 -> 写 0 出参）" % (CAVE_F + 22))
    check(ins_f[6].mnemonic == "jmp" and target_of(ins_f[6]) == WRAP_1C_RESUME,
          "桩F 非空时 `jmp %#x`（回到 `mov eax,[esi]`，栈深度不变）" % WRAP_1C_RESUME)
    check(ins_f[-1].mnemonic == "ret" and ins_f[-1].op_str == "4",
          "桩F 以 `ret 4` 收尾（与 %#x 的调用约定一致：1 个栈参数）" % WRAP_1C)
    check(cb[fo(WRAP_1C_SITE):fo(WRAP_1C_SITE) + 7] == WRAP_1C_OLD,
          "基线 %#x = `and [ebp-4],0; push esi; mov esi,ecx`（正好 7 字节）" % WRAP_1C_SITE)
    i5c = next(md0.disasm(cc[fo(WRAP_1C_SITE):fo(WRAP_1C_SITE) + 7], WRAP_1C_SITE))
    check(i5c.mnemonic == "jmp" and target_of(i5c) == CAVE_F,
          "%#x 变成 `jmp %#x`(桩F)" % (WRAP_1C_SITE, CAVE_F))
    check(cc[fo(WRAP_1C_RESUME):fo(WRAP_1C_RESUME) + 2] ==
          cb[fo(WRAP_1C_RESUME):fo(WRAP_1C_RESUME) + 2] == bytes.fromhex("8b 06"),
          "%#x(`mov eax,[esi]`) 起回归点未动" % WRAP_1C_RESUME)

    # 桩 G（P5d）：0x409EEF 的 this 判空
    exp_g = (bytes.fromhex("85 f6 74 0b 8b 06 8d 4d fc 51")
             + jmp_to(CAVE_G + 10, WRAP_20_RESUME)
             + bytes.fromhex("31 c0 5e c9 c3"))
    check(cave_bytes(CAVE_G, len(exp_g)) == exp_g,
          "桩G 逐字节符合设计：`test esi,esi` -> `je +0x0B`；非空时补做原 6 字节 "
          "`mov eax,[esi] / lea ecx,[ebp-4] / push ecx` 后回归；空分支 `xor eax,eax` "
          "-> `pop esi / leave / ret`")
    ins_g = list(md0.disasm(exp_g, CAVE_G))
    check(ins_g[1].mnemonic == "je" and target_of(ins_g[1]) == CAVE_G + 15,
          "桩G `je %#x`（this==0 -> 返回 0）" % (CAVE_G + 15))
    check(ins_g[5].mnemonic == "jmp" and target_of(ins_g[5]) == WRAP_20_RESUME,
          "桩G 非空时 `jmp %#x`（回到 `push esi`，栈深度不变）" % WRAP_20_RESUME)
    check(ins_g[-1].mnemonic == "ret" and ins_g[-1].op_str == "",
          "桩G 以 `ret` 收尾（与 %#x 的调用约定一致：0 个栈参数）" % WRAP_20)
    check(cb[fo(WRAP_20_SITE):fo(WRAP_20_SITE) + 6] == WRAP_20_OLD,
          "基线 %#x = `mov eax,[esi]; lea ecx,[ebp-4]; push ecx`（正好 6 字节）" % WRAP_20_SITE)
    i5d = next(md0.disasm(cc[fo(WRAP_20_SITE):fo(WRAP_20_SITE) + 6], WRAP_20_SITE))
    check(i5d.mnemonic == "jmp" and target_of(i5d) == CAVE_G,
          "%#x 变成 `jmp %#x`(桩G)" % (WRAP_20_SITE, CAVE_G))
    check(cc[fo(WRAP_20_RESUME):fo(WRAP_20_RESUME) + 3] ==
          cb[fo(WRAP_20_RESUME):fo(WRAP_20_RESUME) + 3] == bytes.fromhex("56 ff 50"),
          "%#x(`push esi; call [eax+0x20]`) 起回归点未动" % WRAP_20_RESUME)

    print()
    print("=" * 74)
    print("5. 无外部分支进入被替换字节区间")
    print("=" * 74)
    all_t = None
    # 全 .text 线性扫描收集分支目标（用于证明"没有外部入口"这一负面命题）
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    tgts = {}
    for i in md.disasm(cb, TEXT_VA):
        if i.mnemonic.startswith("j") or i.mnemonic == "call":
            t = target_of(i)
            if t is not None:
                tgts.setdefault(t, []).append((i.address, i.mnemonic))

    def report(lo, hi, lab, allow=()):
        bad = {}
        for t, v in tgts.items():
            if lo <= t < hi and t not in allow:
                bad[t] = v[:3]
        check(not bad, "%s [%#x,%#x) 无未预期的外部入口 %s" % (lab, lo, hi, bad or ""))

    report(0x403AEB, 0x403AF7, "抛出序言")
    report(0x410FF5, 0x410FFB, "variant 缺陷指令")
    report(0x401D3E, 0x401D44, "WZ 链首解引用")
    # 0x401D52 的唯一外部入口是 0x401DBC 的内层循环回跳（`add edi,4; jmp 0x401d52`），
    # 那里 edi 必然非零，走桩 B 的 `test edi,edi` 会原样通过，行为等价。
    report(0x401D52, 0x401D58, "WZ 数组解引用", allow=(0x401D52,))
    # 0x403965 的唯一外部入口是 0x403961 的 `jmp 0x403965`（同一函数内），
    # 那条路径 esi 就是 this，走桩 D 的 `test esi,esi` 会原样通过。
    report(GETITEM_GUARD_SITE, GETITEM_GUARD_SITE + 5, "get_item 包装缺陷指令",
           allow=(GETITEM_GUARD_SITE,))
    # 0x4039F5 / 0x409EF6 都只能由各自函数入口 0x4039F1 / 0x409EEF 顺序到达。
    report(WRAP_1C_SITE, WRAP_1C_SITE + 7, "vtbl[7] 包装缺陷指令")
    report(WRAP_20_SITE, WRAP_20_SITE + 6, "vtbl[8] 包装缺陷指令")
    for va in P5_GETTER_SITES:
        report(va, va + 5, "取址器调用 %#x" % va)
    report(CAVE_A, CAVE_G + 0x20, "代码桩空洞")

    print()
    print("=" * 74)
    print("6. 禁改区与文件完整性")
    print("=" * 74)
    for lo, hi in FORBIDDEN:
        same = cb[fo(lo):fo(hi)] == cc[fo(lo):fo(hi)]
        check(same, "禁改区 [%#x,%#x) 逐字节未变" % (lo, hi))
    e = struct.unpack_from("<I", cur, 0x3C)[0]
    check(struct.unpack_from("<I", cur, e + 24 + 28)[0] == IMAGE_BASE,
          "ImageBase 仍为 %#x（固定基址，无重定位需求）" % IMAGE_BASE)
    nsec = struct.unpack_from("<H", cur, e + 6)[0]
    check(nsec == struct.unpack_from("<H", base, e + 6)[0], "节数未变 (%d)" % nsec)

    print()
    print("=" * 74)
    if FAILS:
        print("契约测试失败 %d 项：" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("全部契约测试通过。")
    print("  PATCHED_SHA256 %s" % sha256(cur))
    return 0


if __name__ == "__main__":
    sys.exit(main())
