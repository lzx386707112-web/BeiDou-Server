#!/usr/bin/env python3
"""Identify which build of the client actually produced a crash dump.

The fastest way to answer "did my patch take effect on the phone?" is to read
the PE CheckSum recorded for each module inside the minidump and compare it with
the CheckSum of the file on disk.  CheckSum changes with any byte edit (the
reloc hygiene fix changes it, an equal-length code patch changes it), so a match
means "the client really ran this file".

    python3 which_build.py <dump.dmp> [--dll-dir clien] [--all]

Without --all only the compat-layer DLLs and BeiDou.exe are listed.

Why not mtime?  A shared folder (Parallels / Wine drive) may cache by file size,
so a same-length replacement can silently not take effect -- the dump is the
only trustworthy witness.  See memory note 2026-09-24.
"""
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "BeiDouSetItemCompat"))
import fix_dll_reloc_hygiene as H  # noqa: E402

INTEREST = (
    "BeiDou.exe", "BeiDouSetItemCompat.dll", "WzFileLogger.dll",
    "BeiDouDamageSkinCompat.dll", "BeiDouWeatherCompat.dll", "BeiDouVideo.dll",
    "BeiDouVellumVideoCompat.dll", "BeiDouSkillCompatCore.dll",
    "DawnWarriorSkillCompat.dll", "IndexedDamageNumberCompat.dll",
    "KaringSceneCompat.dll", "Canvas.dll", "WzFlashRenderer.dll",
)


def read_dump_modules(path):
    d = open(path, "rb").read()
    sig, ver, n, diroff = struct.unpack_from("<IIII", d, 0)
    if sig != 0x504d444d:
        raise ValueError("not a minidump")
    streams = {}
    for i in range(n):
        t, sz, rva = struct.unpack_from("<III", d, diroff + i * 12)
        if sz:
            streams.setdefault(t, []).append((sz, rva))
    mods = []
    if 4 in streams:
        sz, rva = streams[4][0]
        cnt = struct.unpack_from("<I", d, rva)[0]
        for i in range(cnt):
            off = rva + 4 + i * 108
            base = struct.unpack_from("<Q", d, off)[0]
            size, csum, tds = struct.unpack_from("<III", d, off + 8)
            nrva = struct.unpack_from("<I", d, off + 20)[0]
            nl = struct.unpack_from("<I", d, nrva)[0]
            name = d[nrva + 4:nrva + 4 + nl].decode("utf-16-le", "replace")
            mods.append({"base": base, "size": size, "checksum": csum,
                         "tds": tds, "name": name.split("\\")[-1]})
    return mods, d, streams


def read_exception(d, streams):
    if 6 not in streams:
        return None
    _, rva = streams[6][0]
    tid, _ = struct.unpack_from("<II", d, rva)
    code, flags, rec, addr, nparam = struct.unpack_from("<IIQQI", d, rva + 8)
    params = struct.unpack_from("<15Q", d, rva + 40)
    return {"code": code, "address": addr, "tid": tid,
            "params": [p for p in params[:nparam]]}


def local_checksums(dll_dir):
    out = {}
    for p in glob.glob(os.path.join(dll_dir, "*")):
        try:
            data = bytearray(open(p, "rb").read())
            info = H.read_pe(data)
        except Exception:
            continue
        out[os.path.basename(p).lower()] = {
            "path": p, "checksum": H.pe_checksum(data, info["checksum_off"]),
            "size": len(data)}
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 2
    show_all = "--all" in sys.argv
    dll_dir = "clien"
    for i, a in enumerate(sys.argv[1:]):
        if a == "--dll-dir" and i + 2 <= len(sys.argv[1:]):
            dll_dir = sys.argv[1:][i + 1]
        elif a.startswith("--dll-dir="):
            dll_dir = a.split("=", 1)[1]

    local = local_checksums(dll_dir)
    rc = 0
    for dump in args:
        print(f"\n########## {os.path.basename(dump)}")
        mods, d, streams = read_dump_modules(dump)
        exc = read_exception(d, streams)
        if exc:
            print(f"  异常 code=0x{exc['code']:08X} 地址=0x{exc['address']:08X} "
                  f"参数={[hex(p) for p in exc['params']]}")
            for name in ("BeiDou.exe", "BeiDouSetItemCompat.dll", "WzFileLogger.dll"):
                for m in mods:
                    if m["name"] == name and m["base"] <= exc["address"] < m["base"] + m["size"]:
                        print(f"    -> 落在 {name}+0x{exc['address'] - m['base']:X}")
        print(f"  模块总数={len(mods)}")
        print(f"  {'模块':34s} {'加载基址':>10s} {'转储CheckSum':>14s} "
              f"{'磁盘CheckSum':>14s}  判定")
        rows = [m for m in mods
                if show_all or m["name"] in INTEREST]
        for m in sorted(rows, key=lambda x: x["name"]):
            loc = local.get(m["name"].lower())
            if loc is None:
                verdict = "磁盘无此文件"
            elif loc["checksum"] == m["checksum"]:
                verdict = "== 一致（跑的就是它）"
            else:
                verdict = f"!= 不一致 -> 跑的是 0x{m['checksum']:08X}，盘上是 0x{loc['checksum']:08X}"
                rc = 1
            lstr = f"0x{loc['checksum']:08X}" if loc else "-"
            print(f"  {m['name']:34s} 0x{m['base']:08X} 0x{m['checksum']:012X} "
                  f"{lstr:>14s}  {verdict}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
