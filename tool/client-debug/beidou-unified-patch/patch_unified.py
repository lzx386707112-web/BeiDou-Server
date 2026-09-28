#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BeiDou.exe 统一崩溃补丁（从原始基线一次性打全）

把已经实证过的全部崩溃点，用**同长度原地替换 + .text 尾部零空洞代码桩**
一次性修完，避免"一轮修一个"。

原始基线: sha256 06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18
          PE CheckSum 0x004213DC

补丁清单
--------
P1  0x403AE9  7D -> EB
    `jge +0xc` -> `jmp +0xc`。F_A 里 COM 媒体接口返回失败
    (如 hr=0x80030002 STG_E_FILENOTFOUND) 时不再 push riid/hr 去
    `_com_raise_error`，而是落到 0x403AF7 的正常收尾，沿调用链退化为
    "没有可用对象"。调用方 0x5CAD06 有空值分支，不会再抛。

P2  0x410FF5  8B 08 50 FF 51 04 -> E8 <rel32> 90       (-> 桩 A)
    ATL `_variant_t(IUnknown*, bool fAddRef=true)` 只判了 fAddRef，
    漏判 pSrc。pSrc==NULL 时 `mov ecx,[eax]` 读 0x00000000。
    桩 A 补上判空：为空直接返回（保持合法的空 VT_UNKNOWN）。

P3  0x401D3E  8B 46 20 8B 40 14 85 C0 -> E9 <rel32> 90 90 90  (-> 桩 C)
    WZ/XML 遍历里 `esi` 与 `esi->[0x20]` 两级链式解引用。桩 C 逐级判空，
    为空则令 eax=0 后回到 0x401D44，等价于"该节点没有可遍历内容"。

P4  0x401D52  66 8B 07 66 85 C0 -> E9 <rel32> 90       (-> 桩 B)
    ★ 本次 08:55:02 会话实际崩溃点 (0xC0000005 at BeiDou.exe+0x1D52)。
    `0x401D50 mov edi,eax` 之后的 `mov ax,[edi]` 没有判空：上游
    0x401D48 `je 0x401D4E` 只是把 eax 置 0，代码随即 `mov ax,[edi]`
    解引用 NULL。桩 B 在 edi==0 时跳到外层循环头 0x401D11，与基线里
    "*edi == 0 视为空数组" 的既有语义完全一致。

 注意：P3/P4 只动这两处入口，**不碰** 0x401D58(je 0x401D11)、
 0x401D11(外层循环头) 等既有分支目标。

P5 —— 「切图报无效指针」家族（HRESULT 0x80004003 = E_POINTER）
-------------------------------------------------------------------
症状：切图时弹「无效指针」并退出。「无效指针」不是访问违例，而是
`_com_error`，hr = 0x80004003 = **E_POINTER**。

因果链（已用转储 + 反汇编钉死）：
    媒体/资源对象取不到 -> 本函数把接口缓存槽留成 NULL
    -> 取址器 0x40263B（`cmp [ecx],0 / jne / push 0x80004003 /
       call _com_issue_error`）抛 E_POINTER
    -> 顶层当致命错误处理（弹框 + 退出）。

关键取证（决定修法形状，不要凭直觉改共享函数）：
  * 0x40263B 在 .text 内有 **2406** 个调用点；其中 2381 个把返回值
    直接当 `this` 用。把它改成"返回 0"会把可捕获异常换成 0 地址解引用
    -> **绝对不能动 0x40263B 本体**。
  * 全 .text 中立即数 0x80004003 出现 4927 次 `push` + 402 次 `mov`，
    但 **0 次 `cmp`** —— 没有任何代码"处理" E_POINTER，它只会变成
    致命的 `_com_error`。相反 0x80004002(E_NOINTERFACE) 有 **1404** 次
    `cmp` —— 那才是客户端设计上"接口不可用"的正规降级信号，
    崩溃函数自己在 0x5CAD25 就是这么用的。
  => 所以正确语义是：槽为空时**按"接口不可用"继续（结果为"无数据"）**，
     而不是抛异常。

这一家族由 4 组原地补丁组成，全部只改 5~7 字节操作数或入口 jmp，
所有新代码都放在 .text 尾部零空洞里，可从基线一键重建/回滚：

P5a 0x403965  8B 0E 8D 55 E0 -> E9 <rel32>              (-> 桩 D)
    `0x403965 mov ecx,[esi]` 在 `esi == 0`（this 为空）时读地址 0，必崩。
    基线里走到这里的 esi 只可能来自 0x40263B 的返回值，而它在槽为空时
    就已经抛异常了，所以这条分支在基线中**不可达** —— 本桩只把"必崩"
    变成"空 VARIANT 出参"，本身不改变任何可达行为；
    P5b 去掉抛点后，本桩就是承接空值的落点。
    0x403980 之后的代码以 `leave` 收尾（`leave` 会重置 esp），
    所以从桩 D 直接落到 0x403980 在栈深度上是安全的。

P5b 127 处（见 P5_GETTER_SITES）  E8 <rel32->0x40263B> -> E8 <rel32->桩E>
    ★ 只改**这一个函数内**的 127 个取址器调用点，把目标换成 0x40263B 的
    **容错克隆**（桩 E = `mov eax,[ecx]; ret`）：语义与 0x40263B 的
    正常路径逐字节等价（esi 只是被 push/pop 保护，克隆根本不碰 esi），
    差别只在"槽为空时返回 0 而不是抛 E_POINTER"。
    127 个站点里 ecx 的来法有 3 种编码（`lea disp8(%ebp)` /
    `lea disp32(%ebp)` / 被 `mov dword [ebp-4],imm32` 隔开），
    用"改调用目标"而不是"逐点内联"就一次性覆盖全部编码，且都是
    5 字节操作数原地替换。

P5c 0x4039F5  83 65 FC 00 56 8B F1 -> E9 <rel32> 90 90   (-> 桩 F)
    0x4039F1（`this->vtbl[7](&out)`，`ret 4`，95 个调用者）里
    `0x4039FC mov eax,[esi]` 同样无判空。桩 F 在 ecx==0 时把 0 写进出参
    `*[ebp+8]` 后 `leave; ret 4`（"无数据"），非空时逐字节等价。
    补丁点选在 `and [ebp-4],0 / push esi / mov esi,ecx` 这 7 字节上，
    因为桩必须补做 `push esi`，故回归点是 0x4039FC。

P5d 0x409EF6  8B 06 8D 4D FC 51 -> E9 <rel32> 90         (-> 桩 G)
    0x409EEF（`this->vtbl[8]()` 返回 DWORD，`ret`，182 个调用者）同病。
    桩 G 在 esi==0 时 `xor eax,eax` 后 `leave; ret`（"0 条"），
    非空时逐字节等价。补丁点选在 `mov eax,[esi] / lea ecx,[ebp-4] /
    push ecx` 这 6 字节，回归点 0x409EFC。

  P5c/P5d 改的是共享函数，但触发条件 `this == 0` 在基线里只会导致
  `mov eax,[cs:0]` 访问违例（必崩），所以这两处同样是
  "必崩 -> 有定义的默认值"，不会引入新的崩溃路径。

桩位：.text 尾部空洞（VA 0xAEFE30 起，raw size == vsize == 0x6EF000，
      整段全零、零分支入口、已映射 RX）
      A = 0xAEFE30 (11 B)   B = 0xAEFE40 (23 B)   C = 0xAEFE60 (24 B)
      D = 0xAEFE80 (20 B)
      E = 0xAEFEA0 ( 3 B)   F = 0xAEFEB0 (35 B)   G = 0xAEFEE0 (20 B)
      禁改区 0xAEFA20 (DawnWarriorSkillLoader thunk) 与 0xAEFD80 的既有桩
      都在其之前，不受影响。

用法：
    python3 patch_unified.py --dry-run     # 只校验前置条件
    python3 patch_unified.py --apply       # 真正写盘（幂等）
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_SRC = os.path.join(REPO, "clien", "BeiDou.exe")
BASELINE = os.path.join(HERE, "backup", "BeiDou.exe.orig")

# ---------------------------------------------------------------- PE 布局
IMAGE_BASE = 0x400000
TEXT_RVA = 0x1000
TEXT_RAW = 0x1000
TEXT_RSIZE = 0x6EF000
TEXT_VA = IMAGE_BASE + TEXT_RVA          # 0x401000
TEXT_END_VA = TEXT_VA + TEXT_RSIZE       # 0xAF0000

BASELINE_SHA256 = "06cdac314a6c91f3e133778aa7b72a829778549d4f14e3b95c3589fed541ba18"
BASELINE_CHECKSUM = 0x004213DC

# 禁止触碰的区域（既有 thunk / 桩），补丁前后内容必须完全一致
FORBIDDEN = [
    (0xAEFA20, 0xAEFA40, "DawnWarriorSkillLoader thunk"),
    (0xAEFD80, 0xAEFE00, "既有 .text 尾部桩"),
]

# ---------------------------------------------------------------- 桩地址
CAVE_A = 0xAEFE30      # _variant_t 空指针保护
CAVE_B = 0xAEFE40      # WZ 数组指针空指针保护
CAVE_C = 0xAEFE60      # WZ 节点链式解引用保护
CAVE_D = 0xAEFE80      # IWzProperty get_item 包装的 this 判空
CAVE_E = 0xAEFEA0      # 取址器 0x40263B 的容错克隆（槽空 -> 返回 0）
CAVE_F = 0xAEFEB0      # 0x4039F1 (vtbl[7]) 的 this 判空
CAVE_G = 0xAEFEE0      # 0x409EEF (vtbl[8]) 的 this 判空
CAVE_LIMIT = 0xAF0000  # .text 结束

# ------------------------------------------------- P5：属性取址器（E_POINTER）家族
GETTER = 0x40263B          # `cmpl $0,(%esi)` -> 空则 push 0x80004003 / _com_issue_error
GETITEM_WRAPPER = 0x403935  # get_item 包装：0x403965 `mov ecx,[esi]` 无判空
GETITEM_GUARD_SITE = 0x403965   # P5a 的替换点（5 字节）
GETITEM_RESUME = 0x40396A       # 桩 D 非空时回原流程（push edx / push eax / push esi / call [ecx+0x14]）
GETITEM_EMPTY = 0x403980        # 桩 D 空值时直接落到"把空 VARIANT 拷进出参"

# 另外两个同病包装（0x4039F1 / 0x409EEF）的入口与判空补丁点
WRAP_1C = 0x4039F1              # this->vtbl[7](&out)，ret 4，95 个调用者
WRAP_1C_SITE = 0x4039F5         # `and [ebp-4],0 / push esi / mov esi,ecx`（7 字节）
WRAP_1C_RESUME = 0x4039FC       # 桩 F 非空时回到 `mov eax,[esi]`
WRAP_1C_OLD = bytes.fromhex("83 65 fc 00 56 8b f1")
WRAP_20 = 0x409EEF              # this->vtbl[8]() -> DWORD，ret，182 个调用者
WRAP_20_SITE = 0x409EF6         # `mov eax,[esi] / lea ecx,[ebp-4] / push ecx`（6 字节）
WRAP_20_RESUME = 0x409EFC       # 桩 G 非空时回到 `push esi`
WRAP_20_OLD = bytes.fromhex("8b 06 8d 4d fc 51")

# 崩溃函数 0x5CAC3D..0x5CF58C（单出口 `ret 0xc`，19 KB）内**全部** 127 个
# `call 0x40263B` 站点，按 CFG 可达性枚举并按消费者分组：
#   119 个 -> 0x403935（桩 D 接住空 this）   [P5a 覆盖]
#     6 个 -> 0x4039F1（桩 F 接住）          [P5c 覆盖]
#     2 个 -> 0x409EEF（桩 G 接住）          [P5d 覆盖]
# 全部改调用目标到桩 E，不关心 ecx 的三种编码形式。
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


# ---------------------------------------------------------------- 工具
def va_to_off(va: int) -> int:
    if not (TEXT_VA <= va < TEXT_END_VA):
        raise ValueError("VA %#x 不在 .text 内" % va)
    return va - TEXT_VA + TEXT_RAW


def rel32(src_next_va: int, dst_va: int) -> bytes:
    """从 src_next_va 处（rel32 之后的下一条指令地址）跳到 dst_va。"""
    delta = dst_va - src_next_va
    if not (-0x80000000 <= delta <= 0x7FFFFFFF):
        raise ValueError("跳转超出 rel32 范围: %#x -> %#x" % (src_next_va, dst_va))
    return struct.pack("<i", delta)


def jmp_rel32(at_va: int, dst_va: int) -> bytes:
    return b"\xE9" + rel32(at_va + 5, dst_va)


def call_rel32(at_va: int, dst_va: int) -> bytes:
    return b"\xE8" + rel32(at_va + 5, dst_va)


def pe_checksum(data: bytes) -> int:
    """标准 PE CheckSum 算法（与 patch_flash_slot_guard.py 一致）。"""
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    opt = e_lfanew + 24
    cks_off = opt + 64
    total = 0
    n = len(data)
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


def pe_info(data: bytes):
    e = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e:e + 4] != b"PE\0\0":
        raise SystemExit("不是有效 PE 文件")
    nsec = struct.unpack_from("<H", data, e + 6)[0]
    optsz = struct.unpack_from("<H", data, e + 20)[0]
    opt = e + 24
    checksum = struct.unpack_from("<I", data, opt + 64)[0]
    imagebase = struct.unpack_from("<I", data, opt + 28)[0]
    dllchars = struct.unpack_from("<H", data, opt + 70)[0]
    return dict(e_lfanew=e, nsec=nsec, optsz=optsz, opt=opt,
                checksum=checksum, imagebase=imagebase, dllchars=dllchars)


def find_text_section(data: bytes):
    info = pe_info(data)
    sh = info["e_lfanew"] + 24 + info["optsz"]
    for i in range(info["nsec"]):
        s = sh + i * 40
        name = data[s:s + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rsize, rptr = struct.unpack_from("<IIII", data, s + 8)
        if name == ".text":
            return name, vsize, vaddr, rsize, rptr
    raise SystemExit("找不到 .text 节")


# ---------------------------------------------------------------- 桩代码
def build_cave_a() -> bytes:
    """_variant_t(this, pSrc, fAddRef=true)

    入桩时 [esp] 未变（原始的 `push eax` 尚未执行）。
        85 C0            test eax,eax
        74 06            je   +6        -> 直接 ret（pSrc 为空，保持空的 VT_UNKNOWN）
        8B 08            mov  ecx,[eax]
        50               push eax
        FF 51 04         call [ecx+4]   (AddRef，被调方 ret 4 清栈)
        C3               ret
    """
    code = b"\x85\xC0"          # test eax,eax
    code += b"\x74\x06"         # je -> 末尾 ret
    code += b"\x8B\x08"         # mov ecx,[eax]
    code += b"\x50"             # push eax
    code += b"\xFF\x51\x04"     # call [ecx+4]
    code += b"\xC3"             # ret
    assert len(code) == 11, len(code)
    return code


def build_cave_b() -> bytes:
    """WZ 数组指针空指针保护（替换 0x401D52 的 6 字节）

    基线语义：`mov ax,[edi]` 读数组首个 u16，为 0 则跳到外层循环头 0x401D11。
    edi == 0 时基线会崩；这里把 edi == 0 视作"空数组"，跳到同一个 0x401D11。
    edi != 0 时逐字节等价。

        85 FF                  test edi,edi
        74 0E                  je   末尾(0xAEFE52)
        66 8B 07               mov  ax,[edi]
        66 85 C0               test ax,ax
        E9 <rel32 -> 0x401D58> jmp  0x401D58     (原流程：test 之后)
        90 90 90               nop  (对齐填充)
        E9 <rel32 -> 0x401D11> jmp  0x401D11     (空数组 -> 外层循环)
    """
    at = CAVE_B
    code = b"\x85\xFF"                                  # test edi,edi
    code += b"\x74\x0E"                                 # je 0xAEFE52
    code += b"\x66\x8B\x07"                             # mov ax,[edi]
    code += b"\x66\x85\xC0"                             # test ax,ax
    j1 = at + len(code)
    code += jmp_rel32(j1, 0x401D58)                     # 原流程
    code += b"\x90\x90\x90"                             # 对齐到 j1+13
    j2 = at + len(code)
    assert j2 == at + 0x12, hex(j2 - at)                # 0xAEFE52
    code += jmp_rel32(j2, 0x401D11)                     # 空数组
    # je 目标校验
    assert at + 2 + 2 + 0x0E == j2, "桩 B 的 je 目标算错"
    assert len(code) == 23, len(code)
    return code


def build_cave_c() -> bytes:
    """WZ 节点链式解引用保护（替换 0x401D3E 的 8 字节）

    基线:
        401D3E  mov eax,[esi+0x20]
        401D41  mov eax,[eax+0x14]
        401D44  test eax,eax        <- 桩的回归点
    桩在每一级判空；任一为空则 eax=0 后回到 0x401D44，并且**不跳过**
    0x401D46 的 `mov ebx,edx`（外层循环状态更新）。

        33 C0                  xor  eax,eax
        85 F6                  test esi,esi
        74 0D                  je   末尾(0xAEFE73)
        8B 46 20               mov  eax,[esi+0x20]
        85 C0                  test eax,eax
        74 06                  je   末尾
        8B 40 14               mov  eax,[eax+0x14]
        EB 01                  jmp  末尾
        90                     nop
        E9 <rel32 -> 0x401D44> jmp  0x401D44
    """
    at = CAVE_C
    code = b"\x33\xC0"                                  # xor eax,eax
    code += b"\x85\xF6"                                 # test esi,esi
    code += b"\x74\x0D"                                 # je 0xAEFE73
    code += b"\x8B\x46\x20"                             # mov eax,[esi+0x20]
    code += b"\x85\xC0"                                 # test eax,eax
    code += b"\x74\x06"                                 # je 0xAEFE73
    code += b"\x8B\x40\x14"                             # mov eax,[eax+0x14]
    code += b"\xEB\x01"                                 # jmp 0xAEFE73
    code += b"\x90"                                     # nop
    jt = at + len(code)
    assert jt == at + 0x13, hex(jt - at)                # 0xAEFE73
    code += jmp_rel32(jt, 0x401D44)
    # 三条分支都在 at+4 / at+11 / at+16，各自 +2(自身长度) 后落在 jt
    assert at + 4 + 2 + 0x0D == jt, "桩 C 第一个 je 目标算错"
    assert at + 11 + 2 + 0x06 == jt, "桩 C 第二个 je 目标算错"
    assert at + 16 + 2 + 0x01 == jt, "桩 C 的 jmp 目标算错"
    assert len(code) == 24, len(code)
    return code


# ---------------------------------------------------------------- 补丁表
def build_cave_d() -> bytes:
    """IWzProperty get_item 包装（0x403935）的 `this` 判空

    基线 0x403965 `mov ecx,[esi]` 在 esi == 0 时读地址 0（必崩）。
    基线里 esi 只可能来自取址器 0x40263B 的返回值，而它在槽为空时会抛
    `_com_error`，所以这条分支在基线中**不可达**；本桩把它变成"空出参"。

    入桩现场与基线 0x403965 完全一致（esi=this、eax=pUnk、ebp=帧指针、
    栈深度相同，因为 0x403965 本身没有 push/pop）。`-0x20(%ebp)` 这个临时
    VARIANT 已在 0x403952 由 `call *[0xaf0268]` 构造成空值。

        85 F6                     test esi,esi
        74 0B                     je   D+15            (空 -> 直接出空结果)
        8B 0E                     mov  ecx,[esi]        (原指令)
        8D 55 E0                  lea  edx,-0x20(%ebp)  (原指令)
        E9 <rel32 -> 0x40396A>    jmp  0x40396A        (原流程：三个 push + call [ecx+0x14])
        90                        nop
        E9 <rel32 -> 0x403980>    jmp  0x403980        (把空 VARIANT 拷进出参并返回)

    非空路径逐字节等价（原来 0x403965 那 5 个字节就是 `8B 0E 8D 55 E0`）。
    """
    at = CAVE_D
    code = b"\x85\xF6"                      # test esi,esi
    code += b"\x74\x0B"                     # je D+15
    code += b"\x8B\x0E"                     # mov  ecx,[esi]
    code += b"\x8D\x55\xE0"                 # lea  edx,-0x20(%ebp)
    code += jmp_rel32(at + len(code), GETITEM_RESUME)
    assert len(code) == 14, len(code)
    code += b"\x90"                         # nop（对齐空分支落点）
    assert len(code) == 15, len(code)
    code += jmp_rel32(at + len(code), GETITEM_EMPTY)
    assert at + 2 + 2 + 0x0B == at + 15, "桩 D 的 je 目标算错"
    assert len(code) == 20, len(code)
    return code


def build_cave_e() -> bytes:
    """取址器 0x40263B 的**容错克隆**（槽为空返回 0，不抛 E_POINTER）

    基线 0x40263B：
        56            push esi
        8B F1         mov  esi,ecx
        83 3E 00      cmp  dword [esi],0
        75 0A         jne  0x40264D
        68 03 40 00 80   push 0x80004003        (E_POINTER)
        E8 ...        call _com_issue_error     (不返回)
        8B 06         mov  eax,[esi]            <- 0x40264D
        5E            pop  esi
        C3            ret

    非抛异常的等价路径就是 `eax = *ecx`（`esi` 只是被 push/pop 保护，
    不参与运算，所以克隆根本不碰 esi）。于是：

        8B 01         mov  eax,[ecx]
        C3            ret

    与基线相比只剩一点差别：槽为空时返回 0 而不是抛 `_com_error`。
    标志位与寄存器副作用也与基线一致（mov/ret 不改标志，esi 不变）。
    """
    code = b"\x8B\x01\xC3"      # mov eax,[ecx]; ret
    assert len(code) == 3, len(code)
    return code


def build_cave_f() -> bytes:
    """0x4039F1（`this->vtbl[7](&out)`，`ret 4`）的 this 判空

    基线:
        4039F4  51              push ecx              (分配 [ebp-4])
        4039F5  83 65 FC 00     and  dword [ebp-4],0  <- 补丁点起点
        4039F9  56              push esi
        4039FA  8B F1           mov  esi,ecx
        4039FC  8B 06           mov  eax,[esi]        <- 回归点（= WRAP_1C_RESUME）
        ...
        403A16  8B 45 08        mov  eax,[ebp+8]
        403A19  8B 4D FC        mov  ecx,[ebp-4]
        403A1C  89 08           mov  [eax],ecx        (dword 出参 = [ebp-4])
        403A1E  5E              pop  esi
        403A1F  C9              leave
        403A20  C2 04 00        ret  4

    桩必须补做 7 字节里被替换掉的 `and [ebp-4],0 / push esi / mov esi,ecx`：

        83 65 FC 00      and  dword [ebp-4],0
        56               push esi
        8B F1            mov  esi,ecx
        85 C9            test ecx,ecx
        74 0B            je   +0x0B            (-> off 22：空分支)
        8B 06            mov  eax,[esi]        (原指令)
        E9 <rel32>       jmp  0x4039FC        (原流程，栈深度不变)
        90 90 90 90      nop ×4
        8B 45 08         mov  eax,[ebp+8]      (空分支：把 0 写进出参)
        8B 4D FC         mov  ecx,[ebp-4]
        89 08            mov  [eax],ecx
        5E               pop  esi
        C9               leave
        C2 04 00         ret  4
    """
    at = CAVE_F
    code = b"\x83\x65\xFC\x00"                    # and dword [ebp-4],0
    code += b"\x56"                               # push esi
    code += b"\x8B\xF1"                           # mov  esi,ecx
    code += b"\x85\xC9"                           # test ecx,ecx
    code += b"\x74\x0B"                           # je   F+22
    code += b"\x8B\x06"                           # mov  eax,[esi]
    code += jmp_rel32(at + len(code), WRAP_1C_RESUME)
    assert len(code) == 18, len(code)
    code += b"\x90\x90\x90\x90"                   # 对齐空分支落点
    assert len(code) == 22, len(code)
    code += b"\x8B\x45\x08"                       # mov  eax,[ebp+8]
    code += b"\x8B\x4D\xFC"                       # mov  ecx,[ebp-4]
    code += b"\x89\x08"                           # mov  [eax],ecx
    code += b"\x5E"                               # pop  esi
    code += b"\xC9"                               # leave
    code += b"\xC2\x04\x00"                       # ret  4
    assert at + 9 + 2 + 0x0B == at + 22, "桩 F 的 je 目标算错"
    assert len(code) == 35, len(code)
    return code


def build_cave_g() -> bytes:
    """0x409EEF（`this->vtbl[8]()` 返回 DWORD，`ret`）的 this 判空

    基线:
        409EF2  51              push ecx              (分配 [ebp-4])
        409EF3  56              push esi
        409EF4  8B F1           mov  esi,ecx          (esi = this)
        409EF6  8B 06           mov  eax,[esi]        <- 补丁点起点
        409EF8  8D 4D FC        lea  ecx,[ebp-4]          (= WRAP_20_RESUME 之前)
        409EFB  51              push ecx
        409EFC  56              push esi              <- 回归点
        409EFD  FF 50 20        call [eax+0x20]
        ...
        409F10  8B 45 FC        mov  eax,[ebp-4]      (返回 [ebp-4])
        409F13  5E              pop esi
        409F14  C9              leave
        409F15  C3              ret

    esi 在补丁点之前已经等于 this，所以桩只需补 `mov eax,[esi] /
    lea ecx,[ebp-4] / push ecx` 这 6 字节：

        85 F6            test esi,esi
        74 0B            je   +0x0B            (-> off 15：空分支)
        8B 06            mov  eax,[esi]        (原指令)
        8D 4D FC         lea  ecx,[ebp-4]      (原指令)
        51               push ecx              (原指令)
        E9 <rel32>       jmp  0x409EFC        (原流程，栈深度不变)
        31 C0            xor  eax,eax          (空分支：无数据 -> 0)
        5E               pop  esi
        C9               leave
        C3               ret
    """
    at = CAVE_G
    code = b"\x85\xF6"                            # test esi,esi
    code += b"\x74\x0B"                           # je   G+15
    code += b"\x8B\x06"                           # mov  eax,[esi]
    code += b"\x8D\x4D\xFC"                       # lea  ecx,[ebp-4]
    code += b"\x51"                               # push ecx
    code += jmp_rel32(at + len(code), WRAP_20_RESUME)
    assert len(code) == 15, len(code)
    code += b"\x31\xC0"                           # xor  eax,eax
    code += b"\x5E"                               # pop  esi
    code += b"\xC9"                               # leave
    code += b"\xC3"                               # ret
    assert at + 2 + 2 + 0x0B == at + 15, "桩 G 的 je 目标算错"
    assert len(code) == 20, len(code)
    return code


def build_patches(base: bytes):
    """返回 [(名称, va, 期望原字节, 新字节, 说明), ...]"""
    out = []

    # P1 —— 媒体 COM 失败不抛异常
    out.append(("media-com-skip", 0x403AE9, b"\x7D", b"\xEB",
                "jge +0xc -> jmp +0xc：COM 媒体接口失败不再抛 _com_error"))

    # P2 —— _variant_t 空指针保护
    cave_a = build_cave_a()
    p2_old = b"\x8B\x08\x50\xFF\x51\x04"
    p2_new = call_rel32(0x410FF5, CAVE_A) + b"\x90"
    assert len(p2_new) == 6
    out.append(("variant-null-guard", 0x410FF5, p2_old, p2_new,
                "call 桩A：_variant_t 构造补 pSrc 判空"))

    # P3 —— WZ 链式解引用保护
    # 只替换 0x401D3E..0x401D43 这 6 字节（两条 mov）。
    # 0x401D44 的 `test eax,eax` 必须保留：桩 C 要跳回它来设置 ZF，
    # 否则 0x401D48 的 `je 0x401D4E` 会读到不确定的标志位。
    cave_c = build_cave_c()
    p3_old = b"\x8B\x46\x20\x8B\x40\x14"
    p3_new = jmp_rel32(0x401D3E, CAVE_C) + b"\x90"
    assert len(p3_new) == 6
    out.append(("wz-chain-null-guard", 0x401D3E, p3_old, p3_new,
                "jmp 桩C：esi / esi->[0x20] 逐级判空（保留 0x401D44 的 test）"))

    # P4 —— WZ 数组指针空指针保护（本次实际崩溃点）
    cave_b = build_cave_b()
    p4_old = b"\x66\x8B\x07\x66\x85\xC0"
    p4_new = jmp_rel32(0x401D52, CAVE_B) + b"\x90"
    assert len(p4_new) == 6
    out.append(("wz-array-null-guard", 0x401D52, p4_old, p4_new,
                "jmp 桩B：edi==0 视作空数组，跳过解引用"))

    # P5a —— get_item 包装 0x403935 的 `this` 判空
    cave_d = build_cave_d()
    p5a_old = b"\x8B\x0E\x8D\x55\xE0"
    p5a_new = jmp_rel32(GETITEM_GUARD_SITE, CAVE_D)
    assert len(p5a_new) == 5
    out.append(("wz-getitem-null-guard", GETITEM_GUARD_SITE, p5a_old, p5a_new,
                "jmp 桩D：this==0 时用已构造的空 VARIANT 作出参，不再读地址 0"))

    # P5b —— 崩溃函数内 127 处取址器调用点改指"容错克隆"桩 E
    # 只改 call 的 rel32 操作数（5 字节），不动任何指令编码/寄存器约定。
    cave_e = build_cave_e()
    for va in P5_GETTER_SITES:
        o = va_to_off(va)
        old = bytes(base[o:o + 5])
        if old[0] != 0xE8:
            raise SystemExit("站点 %#x 不是 call rel32：%s" % (va, old.hex(" ")))
        rel = struct.unpack_from("<i", base, o + 1)[0]
        tgt = (va + 5 + rel) & 0xFFFFFFFF
        if tgt != GETTER:
            raise SystemExit("站点 %#x 调的不是 %#X 而是 %#X" % (va, GETTER, tgt))
        new = call_rel32(va, CAVE_E)
        assert len(new) == 5
        out.append(("wz-getter-tolerant-%#x" % va, va, old, new,
                    "取址器改指桩E：槽为空时返回 0（原为抛 _com_error E_POINTER）"))

    # P5c —— 0x4039F1（this->vtbl[7](&out)，ret 4）的 this 判空
    cave_f = build_cave_f()
    p5c_new = jmp_rel32(WRAP_1C_SITE, CAVE_F) + b"\x90\x90"
    assert len(p5c_new) == len(WRAP_1C_OLD) == 7
    out.append(("wz-wrap1c-null-guard", WRAP_1C_SITE, WRAP_1C_OLD, p5c_new,
                "jmp 桩F：this==0 时把 0 写进 dword 出参后 leave/ret 4"))

    # P5d —— 0x409EEF（this->vtbl[8]() -> DWORD，ret）的 this 判空
    cave_g = build_cave_g()
    p5d_new = jmp_rel32(WRAP_20_SITE, CAVE_G) + b"\x90"
    assert len(p5d_new) == len(WRAP_20_OLD) == 6
    out.append(("wz-wrap20-null-guard", WRAP_20_SITE, WRAP_20_OLD, p5d_new,
                "jmp 桩G：this==0 时返回 0（无数据）后 leave/ret"))

    caves = [(CAVE_A, cave_a, "桩A variant-null"),
             (CAVE_B, cave_b, "桩B wz-array-null"),
             (CAVE_C, cave_c, "桩C wz-chain-null"),
             (CAVE_D, cave_d, "桩D wz-getitem-null"),
             (CAVE_E, cave_e, "桩E getter-tolerant"),
             (CAVE_F, cave_f, "桩F wrap1c-null"),
             (CAVE_G, cave_g, "桩G wrap20-null")]
    return out, caves


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(description="BeiDou.exe 统一崩溃补丁")
    ap.add_argument("--apply", action="store_true", help="真正写盘")
    ap.add_argument("--src", default=DEFAULT_SRC, help="目标 BeiDou.exe")
    ap.add_argument("--baseline", default=BASELINE, help="原始基线")
    ap.add_argument("--dry-run", action="store_true", help="只校验（默认行为）")
    args = ap.parse_args()

    print("=" * 72)
    print("BeiDou.exe 统一崩溃补丁")
    print("=" * 72)

    # --- 基线校验
    with open(args.baseline, "rb") as f:
        base = f.read()
    base_sha = hashlib.sha256(base).hexdigest()
    info = pe_info(base)
    print("基线 %s" % args.baseline)
    print("  sha256    = %s" % base_sha)
    print("  CheckSum  = %#010x   ImageBase = %#010x" % (info["checksum"], info["imagebase"]))
    if base_sha != BASELINE_SHA256:
        raise SystemExit("基线 sha256 与预期不符，拒绝继续（期望 %s）" % BASELINE_SHA256)
    if info["checksum"] != BASELINE_CHECKSUM:
        raise SystemExit("基线 CheckSum 与预期不符")
    if info["imagebase"] != IMAGE_BASE:
        raise SystemExit("ImageBase 不是 %#x，PE 布局假设失效" % IMAGE_BASE)
    print("  -> 基线校验通过（这就是转储里 CheckSum=004213dc 的那个版本）")

    name, vsize, vaddr, rsize, rptr = find_text_section(base)
    print("\n.text 节")
    print("  VA=%#x vsize=%#x raw=%#x rsize=%#x" % (vaddr + IMAGE_BASE, vsize, rptr, rsize))
    if (vaddr + IMAGE_BASE, vsize, rptr, rsize) != (TEXT_VA, TEXT_RSIZE, TEXT_RAW, TEXT_RSIZE):
        raise SystemExit("未预期的 .text 布局")
    print("  -> raw size == vsize：尾部空洞在文件与内存里都存在，可安全放桩")

    # --- 空洞全零校验
    total_cave = sum(len(c) for _, c, _ in build_patches(base)[1])
    print("\n代码桩空洞 [%#x, %#x)（本次用到 %d 字节）" % (CAVE_A, CAVE_G + 0x20, total_cave))
    for va in range(CAVE_A, CAVE_G + 0x20):
        if base[va_to_off(va)] != 0:
            raise SystemExit("空洞 %#x 非零，已被占用" % va)
    print("  -> 空洞全零、无占用")

    # --- 禁改区校验
    print("\n禁改区")
    for lo, hi, lab in FORBIDDEN:
        nz = sum(1 for v in range(lo, hi) if base[va_to_off(v)] != 0)
        print("  %#x..%#x  %-32s 非零字节=%d（补丁不会触碰）" % (lo, hi, lab, nz))

    # --- 目标文件状态
    print("\n当前 %s" % args.src)
    cur = None
    if os.path.exists(args.src):
        with open(args.src, "rb") as f:
            cur = f.read()
        print("  sha256 = %s" % hashlib.sha256(cur).hexdigest())
        print("  大小   = %d" % len(cur))
        if len(cur) != len(base):
            raise SystemExit("当前文件大小与基线不同（%d vs %d）" % (len(cur), len(base)))
    else:
        print("  <不存在>（将直接生成）")

    # --- 生成（一律从基线完整生成，不做增量叠加）
    print("\n生成（始终从基线出发）：")
    d = bytearray(base)
    patches, caves = build_patches(base)

    print("\n待应用补丁：")
    tol_sites = []
    for nm, va, old, new, desc in patches:
        o = va_to_off(va)
        actual = bytes(d[o:o + len(old)])
        if actual != old:
            raise SystemExit("补丁 %s 在 %#x 的原始字节不符\n  期望 %s\n  实际 %s"
                             % (nm, va, old.hex(" "), actual.hex(" ")))
        d[o:o + len(new)] = new
        if nm.startswith("wz-getter-tolerant-"):
            tol_sites.append(va)
            continue
        print("  %-22s %#010x  %-23s -> %s" % (nm, va, old.hex(" "), new.hex(" ")))
        print("  %-22s %s" % ("", desc))
    if tol_sites:
        print("  %-22s %d 处  %s" % ("wz-getter-tolerant", len(tol_sites),
                                     " ".join("%#x" % v for v in tol_sites)))
        print("  %-22s %s" % ("", "E8 <rel32->%#x> -> E8 <rel32->%#x>（只改操作数）："
                              "槽为空返回 0，不再抛 _com_error E_POINTER"
                              % (GETTER, CAVE_E)))

    print("\n注入代码桩：")
    for va, blob, lab in caves:
        o = va_to_off(va)
        if bytes(d[o:o + len(blob)]) != b"\x00" * len(blob):
            raise SystemExit("桩位 %#x 不是全零" % va)
        d[o:o + len(blob)] = blob
        print("  %#010x  %-20s %2d 字节  %s" % (va, lab, len(blob), blob.hex(" ")))

    # --- 禁改区复核
    for lo, hi, lab in FORBIDDEN:
        if bytes(d[va_to_off(lo):va_to_off(hi)]) != base[va_to_off(lo):va_to_off(hi)]:
            raise SystemExit("禁改区被破坏：%s" % lab)
    print("\n  -> 禁改区复核通过")

    # --- PE CheckSum
    old_cks = struct.unpack_from("<I", d, info["opt"] + 64)[0]
    struct.pack_into("<I", d, info["opt"] + 64, 0)
    new_cks = pe_checksum(bytes(d))
    struct.pack_into("<I", d, info["opt"] + 64, new_cks)
    print("  PE CheckSum %#010x -> %#010x" % (old_cks, new_cks))

    # --- 算法自检
    chk = pe_checksum(bytes(d))
    if chk != new_cks:
        raise SystemExit("CheckSum 自检失败: 写入 %#x 复算 %#x" % (new_cks, chk))
    print("  -> CheckSum 算法自检通过")

    out = bytes(d)
    diff = [i for i in range(len(base)) if base[i] != out[i]]
    print("\n总差异字节数 = %d（大小不变：%d 字节）" % (len(diff), len(out)))
    if len(out) != len(base):
        raise SystemExit("文件大小改变了，违反原地补丁约束")

    print("\nPATCHED_SHA256 %s" % hashlib.sha256(out).hexdigest())

    if cur is not None and out == cur:
        print("  -> 磁盘上的文件已与本次生成结果完全一致（幂等，无需写盘）")
        return 0
    if cur is not None:
        n = sum(1 for i in range(len(out)) if out[i] != cur[i])
        print("  -> 与磁盘当前版本相差 %d 字节，需要改写" % n)

    if not args.apply:
        print("\n[DRY-RUN] 未写盘。加 --apply 才真正修改。")
        return 0

    with open(args.src, "wb") as f:
        f.write(out)
    print("\n已写入 %s" % args.src)
    return 0


if __name__ == "__main__":
    sys.exit(main())
