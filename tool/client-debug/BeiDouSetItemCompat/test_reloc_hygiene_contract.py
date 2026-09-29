#!/usr/bin/env python3
"""Contract test for fix_dll_reloc_hygiene.classify().

Guards the two verdicts that are easy to confuse and expensive to get wrong:

  stale        fill / dead bytes -- must be stripped, or Wine/Box86 corrupts code
  displacement (in-image address) - (address in a pinned module) -- must be KEPT,
               because the loader adds this DLL's delta and the pinned module's
               base never moves.  Stripping it points the jump at the unmapped
               preferred base: Windows (delta 0) is fine, Android crashes.

Run:  python3 test_reloc_hygiene_contract.py [repo_root]
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fix_dll_reloc_hygiene as H  # noqa: E402

REPO = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", ".."))
CLIEN = os.path.join(REPO, "clien")

FAILS = []


def check(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f"   {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def load(name):
    path = os.path.join(CLIEN, name)
    data = bytearray(open(path, "rb").read())
    return path, data, H.read_pe(data)


def verdicts(data, info, hosts=None):
    _, entries = H.parse_relocs(data, info)
    out = []
    for e in entries:
        v, d = H.classify(data, info, e, hosts)
        out.append((e["rva"], v, d))
    return out


print("== 1) 修复后成品：不得再有任何 stale（可执行段）=")
# 323 -> 363 (2026-09-29): the stat-label patch drops the now-dead HIGHLOW entry
# at RVA 0x3674 and registers 41 for the .titles cave immediates.
# See patch_stat_labels.py / test_stat_labels_contract.py.
for name, expect_total in [("BeiDouSetItemCompat.dll", 363), ("WzFileLogger.dll", 944)]:
    _, data, info = load(name)
    vs = verdicts(data, info)
    stale = [r for r, v, d in vs if v == "stale" and d["exec"]]
    disp = [r for r, v, d in vs if v == "displacement"]
    check(f"{name} 无 stale", not stale, f"stale={[hex(r) for r in stale]}")
    check(f"{name} 无 displacement", not disp, f"disp={[hex(r) for r in disp]}")
    check(f"{name} 条目数 {expect_total}", len(vs) == expect_total, f"got {len(vs)}")

print("\n== 2) BeiDouDamageSkinCompat.dll：2 条跨模块位移必须判为 KEEP ==")
_, ds, ds_info = load("BeiDouDamageSkinCompat.dll")
vs = {r: (v, d) for r, v, d in verdicts(ds, ds_info)}
check("0x1120 是 displacement", vs[0x1120][0] == "displacement", vs[0x1120][0])
check("0x1196 是 displacement", vs[0x1196][0] == "displacement", vs[0x1196][0])
check("无任何 stale", not [r for r, (v, d) in vs.items() if v == "stale"])

# 反推验证：0x1196 的 E9 rel32 必须正好指向本 DLL 首选基址 + 0x1016
BASE = ds_info["image_base"]
SITE = 0x00400000 + 0x37D0F          # BeiDou.exe 里被写入 E9 的位置
value = struct.unpack_from("<I", ds, H.rva_to_off(ds_info, 0x1196))[0]
check("rel32 反推目标 = 首选基址+0x1016",
      (SITE + 5 + value) & 0xFFFFFFFF == BASE + 0x1016,
      f"0x{SITE + 5 + value:08X} vs 0x{BASE + 0x1016:08X}")
check("真实写入点落在 displacement 区间内",
      vs[0x1196][1]["sites"][0] <= SITE + 5 <= vs[0x1196][1]["sites"][1],
      f"sites={[hex(x) for x in vs[0x1196][1]['sites']]}")

disp32 = struct.unpack_from("<I", ds, H.rva_to_off(ds_info, 0x1120))[0]
check("disp32 反推目标 = 首选基址+0x334C",
      (0x00400000 + 0x37D0F + disp32) & 0xFFFFFFFF == BASE + 0x334C,
      f"0x{0x00400000 + 0x37D0F + disp32:08X}")

print("\n== 3) 已确认的 9 条僵尸值：必须一律判为 stale ==")
KNOWN_STALE = {
    "BeiDouSetItemCompat": [0x1D87, 0x1D9A, 0x1E64, 0x1EDC, 0x2849, 0x28CF, 0x28D8],
    "WzFileLogger": [0x24EC, 0x4413],
}
for name, rvas in KNOWN_STALE.items():
    path = os.path.join(CLIEN, name + ".dll")
    data = bytearray(open(path, "rb").read())
    info = H.read_pe(data)
    lo, hi = info["image_base"], info["image_base"] + info["size_of_image"]
    for rva in rvas:
        value = struct.unpack_from("<I", data, H.rva_to_off(info, rva))[0]
        check(f"{name} 0x{rva:04x}=0x{value:08X} 不是位移",
              H.displacement_site(value, lo, hi, H.DEFAULT_HOSTS) is None)

print("\n== 4) Canvas.dll 的条目在非可执行段（--apply 也不得删除）=")
_, cv, cv_info = load("Canvas.dll")
vs = {r: (v, d) for r, v, d in verdicts(cv, cv_info)}
check("0x15A74 不是 displacement", vs[0x15A74][0] == "stale", vs[0x15A74][0])
check("0x15A74 在非可执行段", not vs[0x15A74][1]["exec"], vs[0x15A74][1]["section"])

print("\n== 5) --apply 对 DamageSkinCompat 必须零改动（幂等）=")
before = bytes(ds)
with tempfile.TemporaryDirectory() as td:
    tmp = os.path.join(td, "BeiDouDamageSkinCompat.dll")
    shutil.copyfile(os.path.join(CLIEN, "BeiDouDamageSkinCompat.dll"), tmp)
    rc = H.process(tmp, True, True, H.DEFAULT_HOSTS, False)
    after = open(tmp, "rb").read()
check("process 返回 0", rc == 0)
check("文件逐字节未变", before == after)

print("\n== 6) 分类器边界用例 ==")
HOST = [(0x70000000, 0x100000)]      # 一个高基址"钉住模块"
LO, HI = 0x6FE80000, 0x6FE88000
check("0x90909090 -> stale（SetItem 填充值）",
      H.displacement_site(0x90909090, LO, HI, H.DEFAULT_HOSTS) is None)
check("0x90000041 -> stale（WzFileLogger 错位值）",
      H.displacement_site(0x90000041, LO, HI, H.DEFAULT_HOSTS) is None)
check("非钉住模块的基址不构成解",
      H.displacement_site(0x6FE81000 - 0x50000000, LO, HI, [(0x50000000, 0x8000)]) is not None
      and H.displacement_site((0x50000000 - 0x6FE81000), LO, HI, HOST) is None)
# A=0x6FE81000(本映像) - S=0x70001000(钉住模块) = -0x180000
neg = (0x6FE81000 - 0x70001000) & 0xFFFFFFFF
hit = H.displacement_site(neg, LO, HI, HOST)
check("负位移经 2^32 环绕仍能识别", hit is not None, f"hit={hit}")
if hit:
    (slo, shi), (rlo, rhi) = hit
    check("识别出的站点区间包含真实站点 0x70001000", slo <= 0x70001000 < shi,
          f"sites=({slo:#x},{shi:#x})")
    check("反推出的映内 RVA 区间包含 0x1000", rlo <= 0x1000 < rhi,
          f"rvas=({rlo:#x},{rhi:#x})")

print()
if FAILS:
    print(f"FAILED ({len(FAILS)}): " + "; ".join(FAILS))
    sys.exit(1)
print(f"reloc hygiene contract OK ({CLIEN})")
