#!/usr/bin/env python3
"""BeiDou 客户端 minidump 检查器（Wine/xtajit 友好）。

为什么需要它：本机客户端跑在 Parallels 的 Windows 里，进程由 xtajit(ARM 仿真) 托管，
**所有线程的 CONTEXT.Eip 都读成常量 0x10002**（仿真产物，不是真实指令指针）。
所以只能靠这三样还原现场：

  1. 异常流（Stream 6）—— 里带的 faulting address 是**真实**的；
  2. 线程 CONTEXT 的 Ebp/Esp + 栈内存 —— 可以走 EBP 链；
  3. 会话日志里的 `stack_candidates`（诊断层在异常现场采的样）。

用法：

    python3 dump_inspect.py info      <dump> [--tid 0x2550]   # 模块/异常/线程寄存器/栈扫描
    python3 dump_inspect.py unwind    <dump> [--tid 0x2550]   # EBP 链回溯（默认全部线程）
    python3 dump_inspect.py exc       <dump>                  # 解开异常流：dump C++ 异常对象
                                                             # 0xE06D7363 的 params=[magic, pObj, pTI]
                                                             # pObj(+0x4) 就是 _com_error::m_hr = 真实 HRESULT
    python3 dump_inspect.py mem       <dump> <addr> [size]    # 读任意已转储内存（默认 64 字节）
    python3 dump_inspect.py mods      <dump>                  # 只列模块（便于跨转储比对）
    python3 dump_inspect.py diffmods  <dumpA> <dumpB>         # A 有 B 没有的模块
                                                             # （退出期模块被卸载 = flash 槽位野指针的前置条件）

用 /opt/homebrew/bin/python3 运行（capstone 只装在那个解释器里，本脚本本身不需要）。
"""
import os
import struct
import sys

# MINIDUMP_THREAD，48 字节：0 tid / 4 suspend / 8 priClass / 12 prio / 16 Teb(Q)
# 24 Stack{Start(Q), DataSize(I), Rva(I)} / 40 Context{DataSize(I), Rva(I)}
THREAD_SIZE = 48
# 32 位 CONTEXT（716 字节）
CTX_EDI, CTX_EBP, CTX_EIP, CTX_ESP, CTX_EAX = 156, 180, 184, 196, 176


def load(path):
    d = open(path, "rb").read()
    sig, _, n, diroff = struct.unpack_from("<IIII", d, 0)
    if sig != 0x504d444d:
        raise ValueError(f"{path} 不是 minidump")
    streams = {}
    for i in range(n):
        t, sz, rva = struct.unpack_from("<III", d, diroff + i * 12)
        streams.setdefault(t, []).append((sz, rva))
    return d, streams


def read_modules(d, streams):
    mods = []
    if 4 not in streams:
        return mods
    _, rva = streams[4][0]
    for i in range(struct.unpack_from("<I", d, rva)[0]):
        off = rva + 4 + i * 108
        base = struct.unpack_from("<Q", d, off)[0]
        size, csum = struct.unpack_from("<II", d, off + 8)
        nrva = struct.unpack_from("<I", d, off + 20)[0]
        nl = struct.unpack_from("<I", d, nrva)[0]
        full = d[nrva + 4:nrva + 4 + nl].decode("utf-16-le", "replace")
        mods.append({"base": base, "size": size, "csum": csum,
                     "path": full, "name": full.replace("\\", "/").rsplit("/", 1)[-1]})
    return mods


def read_threads(d, streams):
    ths = []
    if 3 not in streams:
        return ths
    _, rva = streams[3][0]
    for i in range(struct.unpack_from("<I", d, rva)[0]):
        off = rva + 4 + i * THREAD_SIZE
        tid = struct.unpack_from("<I", d, off)[0]
        st_start = struct.unpack_from("<Q", d, off + 24)[0]
        st_size, st_rva = struct.unpack_from("<II", d, off + 32)
        c_dsz, c_rva = struct.unpack_from("<II", d, off + 40)
        ths.append({"tid": tid, "st_start": st_start, "st_size": st_size,
                    "st_rva": st_rva, "c_dsz": c_dsz, "c_rva": c_rva})
    return ths


def read_ranges(d, streams):
    """MemoryList(5) + Memory64List(9) -> [(start, size, file_rva)]"""
    out = []
    for _, rva in streams.get(5, []):
        for i in range(struct.unpack_from("<I", d, rva)[0]):
            off = rva + 4 + i * 16
            start = struct.unpack_from("<Q", d, off)[0]
            dsz, drva = struct.unpack_from("<II", d, off + 8)
            out.append((start, dsz, drva))
    for _, rva in streams.get(9, []):
        cnt, base = struct.unpack_from("<QQ", d, rva)
        p = rva + 16
        for _ in range(cnt):
            start, dsz = struct.unpack_from("<QQ", d, p)
            out.append((start, dsz, base))
            base += dsz
            p += 16
    return out


def read_exception(d, streams):
    if 6 not in streams:
        return None
    _, rva = streams[6][0]
    tid, _ = struct.unpack_from("<II", d, rva)
    code, _flags, _rec, addr, nparam = struct.unpack_from("<IIQQI", d, rva + 8)
    params = struct.unpack_from("<15Q", d, rva + 40)
    return {"tid": tid, "code": code, "addr": addr, "params": params[:nparam]}


def read_ctx(d, t):
    if not t["c_dsz"]:
        return None
    r = t["c_rva"]
    c = {"flags": struct.unpack_from("<I", d, r)[0]}
    for k, off in (("eax", CTX_EAX), ("ebp", CTX_EBP), ("eip", CTX_EIP), ("esp", CTX_ESP)):
        c[k] = struct.unpack_from("<I", d, r + off)[0]
    return c


def resolver(mods):
    def f(addr):
        for m in mods:
            if m["base"] <= addr < m["base"] + m["size"]:
                return f"{m['name']}+0x{addr - m['base']:X}"
        return None
    return f


def stack_bytes(d, t, ranges):
    """线程栈：优先用线程自带的 Stack 描述，缺了就从内存范围表里找。

    2026-09-28：自家 first-chance 转储（BeiDouVellumVideoCompat.dll 写的那份）里，
    ThreadList 中每个线程的 Stack 描述**恒为 rva=0** —— 但内存范围表里确实有一段
    覆盖该线程栈的段（实测主线程 st_start=0x001AE780，表里是 0x001AE6EC..0x001B02F0）。
    旧实现只认「起点完全相等」，于是所有自家转储都报「栈未落在转储里」。
    现在：完全相等优先，其次接受**包含** st_start 的段（取其中起点最高的一个）。
    """
    if t["st_rva"] and t["st_size"]:
        blob = d[t["st_rva"]:t["st_rva"] + t["st_size"]]
        if len(blob) >= t["st_size"]:
            return t["st_start"], blob
    best = None
    for start, dsz, drva in ranges:
        if start == t["st_start"]:
            return start, d[drva:drva + dsz]
        if start <= t["st_start"] < start + dsz and (best is None or start > best[0]):
            best = (start, dsz, drva)
    if best is not None:
        start, dsz, drva = best
        return start, d[drva:drva + dsz]
    return None, None


def read_mem(d, ranges):
    def rd(addr, size=4):
        for start, dsz, drva in ranges:
            if start <= addr and addr + size <= start + dsz:
                return d[drva + (addr - start):drva + (addr - start) + size]
        return None
    return rd


def cmd_info(path, want_tid):
    d, streams = load(path)
    mods, ths, ranges = read_modules(d, streams), read_threads(d, streams), read_ranges(d, streams)
    res = resolver(mods)
    exc = read_exception(d, streams)
    print(f"# {os.path.basename(path)}  size={len(d)}  modules={len(mods)}  threads={len(ths)}")
    print(f"# streams={ {k: v[0][0] for k, v in streams.items()} }")
    if exc:
        print(f"# EXCEPTION tid=0x{exc['tid']:X} code=0x{exc['code']:08X} "
              f"addr=0x{exc['addr']:08X} -> {res(exc['addr'])} "
              f"params={[hex(p) for p in exc['params']]}")
    else:
        print("# 无异常流（不是 AV 崩溃；window_lost / exit-process 这类转储本来就没有）")
    for t in ths:
        if want_tid is not None and t["tid"] != want_tid:
            continue
        c = read_ctx(d, t)
        if c is None:
            continue
        note = "  <-- EIP 是 xtajit 常量，弃用" if c["eip"] == 0x10002 else ""
        print(f"\n== tid=0x{t['tid']:X} ({t['tid']}) eip=0x{c['eip']:08X}{note}")
        print(f"   esp=0x{c['esp']:08X} ebp=0x{c['ebp']:08X} eax=0x{c['eax']:08X} "
              f"stack=[0x{t['st_start']:X}+0x{t['st_size']:X}]")
        start, blob = stack_bytes(d, t, ranges)
        if blob is None:
            print("   （该线程栈未落在转储里）")
            continue
        hits = []
        for off in range(0, len(blob) - 3, 4):
            v = struct.unpack_from("<I", blob, off)[0]
            f = res(v)
            if f:
                hits.append((start + off, v, f))
        print(f"   落在模块内的 dword：{len(hits)} 个（前 24 个）")
        for a, v, f in hits[:24]:
            tag = " <-esp" if a == c["esp"] else (" <-ebp" if a == c["ebp"] else "")
            print(f"     {a:#010x}: {v:#010x}  {f}{tag}")


def cmd_unwind(path, want_tid):
    d, streams = load(path)
    mods, ths, ranges = read_modules(d, streams), read_threads(d, streams), read_ranges(d, streams)
    res, rd = resolver(mods), read_mem(d, ranges)
    print(f"##### {os.path.basename(path)}")
    for t in ths:
        if want_tid is not None and t["tid"] != want_tid:
            continue
        c = read_ctx(d, t)
        if c is None:
            continue
        start, blob = stack_bytes(d, t, ranges)
        print(f"\n== tid=0x{t['tid']:X} ebp=0x{c['ebp']:010X} esp=0x{c['esp']:010X}")
        cur = c["ebp"]
        for depth in range(48):
            if blob is None or not (start <= cur and cur + 8 <= start + len(blob)):
                print(f"   [{depth:2}] ebp=0x{cur:010X} 越出栈范围 -> 停")
                break
            pair = rd(cur, 8)
            if pair is None:
                print(f"   [{depth:2}] ebp=0x{cur:010X} 不可读 -> 停")
                break
            nxt, ret = struct.unpack("<II", pair)
            name = res(ret) or ("?" if ret else "0")
            print(f"   [{depth:2}] ebp=0x{cur:010X} ret=0x{ret:010X}  {name}")
            if nxt <= cur:
                break
            cur = nxt


# 常见 HRESULT —— 客户端错误框里显示的就是这个十进制数（-2147467261 = 0x80004003）
HRESULTS = {
    0x00000000: "S_OK",
    0x80004001: "E_NOTIMPL",
    0x80004002: "E_NOINTERFACE  不支持此接口",
    0x80004003: "E_POINTER      无效指针",
    0x80004005: "E_FAIL",
    0x8007000E: "E_OUTOFMEMORY",
    0x80030001: "STG_E_INVALIDFUNCTION",
    0x80030002: "STG_E_FILENOTFOUND",
    0x80030003: "STG_E_PATHNOTFOUND",
    0x88760028: "DDERR_INVALIDPARAMS",
    0x8876017C: "DDERR_OUTOFVIDEOMEMORY",
    0x88760212: "DDERR_SURFACELOST",
    0x8876086C: "D3DERR_DEVICELOST",
    0x88760868: "D3DERR_DEVICENOTRESET",
}


def hrname(v):
    if v in HRESULTS:
        return HRESULTS[v]
    if v >= 0x80000000:
        return f"(失败 HRESULT, signed {v - 0x100000000})"
    return None


def dump_blob(blob, addr, res):
    for off in range(0, len(blob) & ~15, 16):
        row = blob[off:off + 16]
        print(f"   0x{addr + off:08X}  " + " ".join(f"{b:02x}" for b in row))
    print("   -- dwords --")
    for off in range(0, len(blob) - 3, 4):
        v = struct.unpack_from("<I", blob, off)[0]
        notes = []
        h = hrname(v)
        f = res(v)
        if h:
            notes.append(h)
        if f:
            notes.append(f"[{f}]")
        if notes:
            print(f"   +0x{off:02X}: 0x{v:08X}  {'  '.join(notes)}")


def cmd_mem(path, addr, size=64):
    d, streams = load(path)
    mods, ranges = read_modules(d, streams), read_ranges(d, streams)
    res, rd = resolver(mods), read_mem(d, ranges)
    print(f"# {os.path.basename(path)}  read 0x{addr:08X}..0x{addr + size:08X}")
    blob = rd(addr, size)
    if blob is not None:
        dump_blob(blob, addr, res)
        return
    parts = [(max(s, addr), min(s + z, addr + size), r)
             for s, z, r in ranges if s < addr + size and s + z > addr]
    if not parts:
        print("   （该地址不在转储的内存范围里）")
        return
    for lo, hi, r in sorted(parts):
        print(f"   片段 [0x{lo:08X}..0x{hi:08X}]")
        dump_blob(d[r + (lo - min(s for s, _, _ in parts)):][:hi - lo], lo, res)


def cmd_exc(path):
    d, streams = load(path)
    mods, ranges = read_modules(d, streams), read_ranges(d, streams)
    res, rd = resolver(mods), read_mem(d, ranges)
    exc = read_exception(d, streams)
    print(f"# {os.path.basename(path)}")
    if not exc:
        print("# 无异常流 —— 不是 AV/C++ 崩溃转储（window_lost / exit-process / hang 这类本来就没有）")
        return
    p = exc["params"]
    print(f"# EXCEPTION tid=0x{exc['tid']:X} code=0x{exc['code']:08X} "
          f"addr=0x{exc['addr']:08X} -> {res(exc['addr'])}")
    print(f"# params={[hex(x) for x in p]}")
    if exc["code"] != 0xE06D7363 or len(p) < 3:
        print("# （不是 MSVC C++ throw，不做对象解读）")
        return
    pobj, pti = p[1], p[2]
    print(f"# MSVC C++ throw：magic=0x{p[0]:08X}(应为 0x19930520) "
          f"pObject=0x{pobj:08X} pThrowInfo=0x{pti:08X}")
    blob = rd(pobj, 64)
    if blob is None:
        print(f"\n== 异常对象 0x{pobj:08X} 不在转储内存里，无法解读")
        return
    print(f"\n== 异常对象 0x{pobj:08X}（_com_error： +0x0 vtable(若有) / +0x4 m_hr）")
    dump_blob(blob, pobj, res)
    hr = struct.unpack_from("<I", blob, 4)[0]
    hn = hrname(hr)
    if hn:
        print(f"\n>> +0x4 —— 很可能是 m_hr = 0x{hr:08X}  ({hn})")


class PE:
    """只为"读一条指令的字节"服务的最小 PE32 读取器。

    minidump 的 MemoryList 通常**不含模块的代码页**（本工程实测 BeiDou.exe 的 .text
    就不在转储里），于是"栈上的值是不是返回地址"没法用转储里的代码字节验证。
    模块文件就在 clien/ 下，直接按 RVA 换算文件偏移读即可。
    """

    def __init__(self, path):
        self.path = path
        b = open(path, "rb").read()
        self.b = b
        pe = struct.unpack_from("<I", b, 0x3C)[0]
        if b[pe:pe + 4] != b"PE\0\0":
            raise ValueError(f"{path} 不是 PE")
        nsec = struct.unpack_from("<H", b, pe + 6)[0]
        optsz = struct.unpack_from("<H", b, pe + 20)[0]
        opt = pe + 24
        self.image_base = struct.unpack_from("<I", b, opt + 28)[0]
        self.sections = []
        p = opt + optsz
        for _ in range(nsec):
            vsz, va, rsz, raw = struct.unpack_from("<IIII", b, p + 8)
            self.sections.append((va, max(vsz, rsz), raw))
            p += 40

    def read_va(self, va, size):
        rva = va - self.image_base
        for va0, sz, raw in self.sections:
            if va0 <= rva < va0 + sz:
                off = raw + (rva - va0)
                chunk = self.b[off:off + size]
                return chunk if len(chunk) == size else None
        return None


def load_pe_map(dll_dir):
    """模块名 -> PE；名字大小写不敏感。找不到的模块留空，交由调用方回退。"""
    out = {}
    if not dll_dir or not os.path.isdir(dll_dir):
        return out
    for fn in os.listdir(dll_dir):
        p = os.path.join(dll_dir, fn)
        if not os.path.isfile(p):
            continue
        try:
            out[fn.lower()] = PE(p)
        except Exception:
            pass
    return out


def cmd_mods(path):
    d, streams = load(path)
    for m in sorted(read_modules(d, streams), key=lambda x: x["base"]):
        print(f"0x{m['base']:08X} 0x{m['size']:08X} csum=0x{m['csum']:08X} {m['name']}")



def looks_like_prologue(b):
    """函数入口的常见开头。E8 直接调用的目标必须是真函数入口，否则是巧合。"""
    if not b:
        return False
    if b[0] == 0x55 and len(b) > 2 and b[1] == 0x8B and b[2] == 0xEC:
        return True
    if b[0] in (0x53, 0x56, 0x57, 0x51):          # push reg
        return True
    if b[0] == 0x6A:                              # push imm8
        return True
    if b[0] == 0x83 and len(b) > 1 and b[1] == 0xEC:   # sub esp,imm8
        return True
    if b[0] == 0x81 and len(b) > 1 and b[1] == 0xEC:   # sub esp,imm32
        return True
    if b[0] == 0xB8:                              # mov eax,imm32（本工程 E8 桩常见）
        return True
    if b[0] == 0x8B and len(b) > 2 and b[1] == 0xFF and b[2] == 0x55:
        return True
    if b[0] == 0xCC:                              # 填充（可能是跳转表项）
        return True
    return False


def call_before(rd, v, owner, pes):
    """V 是返回地址时，找出它前面那条 call：返回 (call_site, callee_or_None, 描述)。

    覆盖这个二进制里实际出现的三种，并且**要求语义成立**，否则 UTF-16 字符串
    之类的栈数据会碰巧命中：
      E8 rel32      —— callee 必须落在同一模块且开头像函数入口
      FF 15 imm32   —— imm32 处必须存着一个指向已加载模块的指针（IAT/.data 指针）
      FF /2 [reg+disp] —— 只有 3 字节形态采用（6 字节无 modrm 语义验证，误报太多）
    """
    def read_any(a, n):
        b = rd(a, n)
        if b is not None:
            return b
        m = owner(a)
        if m is None:
            return None
        pe = pes.get(m["name"].lower())
        if pe is None:
            return None
        return pe.read_va(a, n)

    p6 = read_any(v - 6, 6)
    if p6 and p6[0] == 0xFF and p6[1] == 0x15:
        slot = struct.unpack_from("<I", p6, 2)[0]
        sb = read_any(slot, 4)
        if sb:
            ptr = struct.unpack_from("<I", sb, 0)[0]
            tm = owner(ptr)
            if tm and ptr > 0x10000:
                return v - 6, ptr, f"FF 15 (call *[0x{slot:08X}])"
        return None
    p5 = read_any(v - 5, 5)
    if p5 and p5[0] == 0xE8:
        rel = struct.unpack_from("<i", p5, 1)[0]
        callee = (v + rel) & 0xFFFFFFFF
        if owner(callee) is owner(v):
            if looks_like_prologue(read_any(callee, 3)):
                return v - 5, callee, "E8 (call rel32)"
        return None
    p3 = read_any(v - 3, 3)
    if p3 and p3[0] == 0xFF and (p3[1] & 0xC0) == 0x40 and ((p3[1] >> 3) & 7) == 2:
        return v - 3, None, "FF /2 (call *[reg+disp8])"
    return None


def cmd_rets(path, want_tid, dll_dir):
    """在栈上找**真返回地址**：值为 V，且 V 前面确实是一条 call 指令。

    这是 xtajit 环境下唯一可靠的上行调用链恢复方式 —— EIP 恒为 0x10002，
    EBP 链在异常/无帧指针函数里立刻断。返回地址不需要帧指针，只要 call 还在。

    代码字节优先取转储内存，转储里没有该模块的代码页时回退读 --dll-dir 下的模块文件。
    """
    d, streams = load(path)
    mods, ths, ranges = read_modules(d, streams), read_threads(d, streams), read_ranges(d, streams)
    res, rd = resolver(mods), read_mem(d, ranges)
    pes = load_pe_map(dll_dir)
    hits_local = 0

    def owner(addr):
        for m in mods:
            if m["base"] <= addr < m["base"] + m["size"]:
                return m
        return None

    def reader_for(addr):
        """返回 (读字节函数, 来源标签)。代码页在转储里就用转储，否则用磁盘文件。"""
        m = owner(addr)
        if m is None:
            return None, None
        def from_dump(a, n):
            return rd(a, n)
        if from_dump(addr, 1) is not None:
            return from_dump, "dump"
        pe = pes.get(m["name"].lower())
        if pe is None:
            return None, None
        return pe.read_va, os.path.basename(pe.path)

    print(f"##### {os.path.basename(path)}  —— 栈上真返回地址（前置 call 校验通过）")
    for t in ths:
        if want_tid is not None and t["tid"] != want_tid:
            continue
        c = read_ctx(d, t)
        if c is None:
            continue
        start, blob = stack_bytes(d, t, ranges)
        if blob is None:
            continue
        found = []
        for off in range(0, len(blob) - 3, 4):
            v = struct.unpack_from("<I", blob, off)[0]
            m = owner(v)
            if not m:
                continue
            rdr, src = reader_for(v)
            if rdr is None:
                continue
            cb = call_before(rd, v, owner, pes)
            if not cb:
                continue
            site, callee, kind = cb
            if src != "dump":
                hits_local += 1
            found.append((start + off, v, m, site, callee, kind, src))
        print(f"\n== tid=0x{t['tid']:X}  esp=0x{c['esp']:08X}  命中 {len(found)}")
        for a, v, m, site, callee, kind, src in found:
            cal = f" -> {res(callee)}" if callee else ""
            print(f"   栈 0x{a:08X}  ret {v:#010x} [{m['name']}+0x{v - m['base']:X}]"
                  f"   <- {kind} @0x{site:08X}{cal}   [{src}]")


def cmd_diffmods(a, b):
    da, sa = load(a)
    db, sb = load(b)
    ma = {m["name"].lower(): m for m in read_modules(da, sa)}
    mb = {m["name"].lower(): m for m in read_modules(db, sb)}
    print(f"A={os.path.basename(a)} ({len(ma)} mods)  B={os.path.basename(b)} ({len(mb)} mods)")
    gone = sorted(set(ma) - set(mb))
    print(f"\n== A 有、B 没有（退出期被卸载的模块，共 {len(gone)}）")
    for k in gone:
        print(f"   - {ma[k]['path']}  base=0x{ma[k]['base']:08X}")
    new = sorted(set(mb) - set(ma))
    if new:
        print(f"\n== B 有、A 没有（共 {len(new)}）")
        for k in new:
            print(f"   + {mb[k]['path']}  base=0x{mb[k]['base']:08X}")


def main():
    argv = sys.argv[1:]
    tid = None
    dll_dir = "clien"
    rest = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--tid":
            tid = int(argv[i + 1], 16)
            i += 2
            continue
        if a == "--dll-dir":
            dll_dir = argv[i + 1]
            i += 2
            continue
        rest.append(a)
        i += 1
    if not rest:
        print(__doc__)
        return 2
    cmd, files = rest[0], rest[1:]
    if cmd == "info" and files:
        cmd_info(files[0], tid)
    elif cmd == "unwind" and files:
        cmd_unwind(files[0], tid)
    elif cmd == "exc" and files:
        cmd_exc(files[0])
    elif cmd == "mem" and len(files) >= 2:
        cmd_mem(files[0], int(files[1], 16),
                int(files[2], 16) if len(files) > 2 else 64)
    elif cmd == "rets" and files:
        cmd_rets(files[0], tid, dll_dir)
    elif cmd == "mods" and files:
        cmd_mods(files[0])
    elif cmd == "diffmods" and len(files) >= 2:
        cmd_diffmods(files[0], files[1])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
