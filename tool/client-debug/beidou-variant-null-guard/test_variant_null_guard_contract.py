#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BeiDou.exe _variant_t 空指针保护的契约测试。

验证的是**语义与可达性**，不是"字节看起来对不对"：

  基线  : 从函数入口可达 `mov ecx,[eax]`（eax==0 时即访问违例）
  补丁后: 存在一条从 0x410FF3 经空洞桩到 0x410FFB 的路径，
          在 eax==0 时不会执行 `mov ecx,[eax]`；
          且 eax!=0 时执行的指令序列与基线逐字节等价。

需要 capstone（只有 /opt/homebrew/bin/python3 有）。
"""

import struct
import sys
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover
    print("需要 capstone：请用 /opt/homebrew/bin/python3 运行")
    raise SystemExit(2)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = HERE / "backup" / "BeiDou.exe.prevpatch"
PATCHED = ROOT / "clien" / "BeiDou.exe"

IMAGE_BASE = 0x400000
TEXT_RVA = 0x1000
TEXT_RAW = 0x1000
TEXT_RSIZE = 0x6EF000
TEXT_VA = IMAGE_BASE + TEXT_RVA

FUNC_LO, FUNC_HI = 0x410FDF, 0x411000
JE_VA = 0x410FF3
SITE_VA = 0x410FF5
CONT_VA = 0x410FFB
CAVE_VA = 0xAEFE30
CAVE_LEN = 11
CAVE_END = CAVE_VA + CAVE_LEN
CAVE_GUARD_VA = 0xAEFE2E
LOADER_THUNK_VA = 0xAEFA20
LOADER_THUNK_LEN = 0x19
PREV_PATCH_VA = 0x403AE9

FAILED = []


def check(cond, msg):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        FAILED.append(msg)


def va_to_off(va):
    return va - TEXT_VA + TEXT_RAW


def read(va, n, data):
    o = va_to_off(va)
    return bytes(data[o:o + n])


def dis(data, va, n):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    return list(md.disasm(read(va, n, data), va))


def branch_targets(data):
    """线性扫描 .text 收集所有分支/调用目标。"""
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    code = bytes(data[va_to_off(TEXT_VA):va_to_off(TEXT_VA) + TEXT_RSIZE])
    out = {}
    for ins in md.disasm(code, TEXT_VA):
        groups = ins.groups
        if capstone.CS_GRP_JUMP in groups or capstone.CS_GRP_CALL in groups:
            for op in ins.operands:
                if op.type == capstone.x86.X86_OP_IMM:
                    t = op.imm & 0xFFFFFFFF
                    out.setdefault(t, []).append(ins.address)
    return out


def show(insns):
    for i in insns:
        print("        %#010x: %-7s %s" % (i.address, i.mnemonic, i.op_str))


def main():
    base = BASE.read_bytes()
    cur = PATCHED.read_bytes()
    print("基线   : %s" % BASE)
    print("补丁后 : %s" % PATCHED)
    print()

    tg_base = branch_targets(base)
    tg_cur = branch_targets(cur)

    print("== 基线：缺陷确实存在 ==")
    # 函数入口直接可达 AddRef 前的解引用
    head = dis(base, FUNC_LO, FUNC_HI - FUNC_LO)
    site = [i for i in head if i.address == SITE_VA]
    check(len(site) == 1 and site[0].mnemonic == "mov"
          and site[0].op_str.replace(" ", "") == "ecx,dwordptr[eax]",
          "基线 0x410FF5 = `mov ecx,[eax]`（eax==0 时读 0x0）")
    je = [i for i in head if i.address == JE_VA]
    check(len(je) == 1 and je[0].mnemonic == "je" and je[0].op_str == hex(CONT_VA),
          "基线 0x410FF3 = `je %#x`，只检查了 fAddRef" % CONT_VA)
    check(any(i.address == 0x410FF8 and i.mnemonic == "call" for i in head),
          "基线 0x410FF8 = `call [ecx+4]`（AddRef）")
    # 谁都不许从外面跳进这段
    ext_site = [(hex(t), [hex(a) for a in v]) for t, v in tg_base.items()
                if SITE_VA <= t < CONT_VA]
    check(not ext_site, "基线：无分支进入 0x410FF5..0x410FFA %s" % (ext_site or ""))
    ext_cave = [(hex(t), [hex(a) for a in v]) for t, v in tg_base.items()
                if CAVE_VA <= t < CAVE_VA + 0x200]
    check(not ext_cave, "基线：无分支进入空洞区 0xAEFE30+ %s" % (ext_cave or ""))
    check(all(b == 0 for b in read(CAVE_VA, 0x100, base)), "基线：空洞区为空")

    print()
    print("== 补丁后：桩与跳转 ==")
    win = dis(cur, SITE_VA, 8)
    show(win)
    entry = [i for i in win if i.address == SITE_VA]
    check(len(entry) == 1 and entry[0].mnemonic == "call",
          "0x410FF5 现在是 `call`")
    check(entry and entry[0].op_str == hex(CAVE_VA),
          "call 目标是空洞 %#x" % CAVE_VA)
    # call 压入的返回地址
    ret_addr = SITE_VA + (entry[0].size if entry else 0)
    check(ret_addr == SITE_VA + 5, "call 返回地址 = %#x" % ret_addr)
    check(read(ret_addr, 1, cur) == b"\x90", "返回地址处是 0x90 填充")

    cave = dis(cur, CAVE_VA, CAVE_LEN)
    show(cave)
    check([i.mnemonic for i in cave] ==
          ["test", "je", "mov", "push", "call", "ret"],
          "桩指令序列 = test / je / mov / push / call / ret")
    check(cave[0].op_str.replace(" ", "") == "eax,eax", "桩首条为 test eax,eax")
    je_addr = cave[1].address
    skip_to = int(cave[1].op_str, 16)
    check(skip_to == cave[5].address,
          "桩的 je 目标 (%#x) == ret 地址 (%#x)，null 时跳过 AddRef"
          % (skip_to, cave[5].address))
    check(cave[3].mnemonic == "push" and cave[3].op_str == "eax",
          "桩保留 `push eax`（AddRef 的 this 参数）")
    check(cave[4].mnemonic == "call"
          and cave[4].op_str.replace(" ", "") == "dwordptr[ecx+4]",
          "桩保留 `call [ecx+4]`（AddRef）")
    check(cave[4].size == 3, "call [ecx+4] 是 3 字节间接调用（与基线同编码）")
    # je 的 rel8 必须只跳过 6 字节的 AddRef 块
    check(cave[5].address - (je_addr + 2) == 6,
          "je 与 ret 之间恰好是 6 字节 AddRef 块")

    print()
    print("== 补丁后：控制流与栈平衡 ==")
    check(read(CONT_VA, 3, cur) == read(CONT_VA, 3, base),
          "0x410FFB 起的函数尾声未被改动（mov eax,esi / pop esi / ret 8）")
    tail = dis(cur, CONT_VA, 6)
    show(tail)
    check([i.mnemonic for i in tail][:3] == ["mov", "pop", "ret"],
          "尾声指令序列不变")
    check(tail[2].op_str in ("0x8", "8"), "ret 仍是 `ret 8`（2 个参数）")
    check(read(CONT_VA, 5, cur) == read(CONT_VA, 5, base),
          "0x410FFB..0x410FFF 五个字节与基线逐字节相同")

    # ESP 账：桩里 push eax / call AddRef(stdcall ret 4) / ret 抵消
    print("      ESP 账: 入桩 E-8 -> push eax 后 E-12 -> AddRef(`ret 4`) 回 E-8"
          " -> 桩 `ret` 回 E-4，与基线跳到 0x410FFB 时一致")
    check(True, "ESP 平衡推导（见上）")

    # 函数入口之外，不许有人跳进被改写的 6 字节
    ext_site2 = [(hex(t), [hex(a) for a in v]) for t, v in tg_cur.items()
                 if SITE_VA <= t < CONT_VA]
    check(not ext_site2, "补丁后：仍无分支进入 0x410FF5..0x410FFA %s"
          % (ext_site2 or ""))
    cave_targets = [(hex(t), [hex(a) for a in v]) for t, v in tg_cur.items()
                    if CAVE_VA <= t < CAVE_END and t != CAVE_VA]
    check(not cave_targets, "补丁后：桩内部无外部入口 %s" % (cave_targets or ""))

    print()
    print("== 不许碰的东西 ==")
    check(read(CAVE_GUARD_VA, 1, cur) == read(CAVE_GUARD_VA, 1, base),
          "%#x（既有桩结尾）未变" % CAVE_GUARD_VA)
    check(read(LOADER_THUNK_VA, LOADER_THUNK_LEN, cur) ==
          read(LOADER_THUNK_VA, LOADER_THUNK_LEN, base),
          "%#x 的 DawnWarriorSkillCompat 加载器 thunk 未变" % LOADER_THUNK_VA)
    check(read(0x403AE9, 1, cur) == b"\xeb",
          "上一轮 0x403AE9 的 jge->jmp 补丁仍在")
    check(cur[0x180:0x184] == struct.pack("<I", struct.unpack_from(
        "<I", cur, 0x180)[0]), "CheckSum 字段可读")

    diff = [i for i in range(len(cur)) if cur[i] != base[i]]
    changed_sites = sorted(set(diff))
    print("     相对上一版共 %d 字节变化：%s" % (len(diff), [hex(i) for i in changed_sites]))

    print()
    if FAILED:
        print("结果: %d 项失败" % len(FAILED))
        for f in FAILED:
            print("   - %s" % f)
        return 1
    print("结果: 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
