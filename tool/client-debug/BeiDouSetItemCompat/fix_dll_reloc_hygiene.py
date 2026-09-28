#! /usr/bin/env python3
r"""Repair stale PE base relocations in a hand-patched compatibility DLL.

Why this exists
---------------
A HIGHLOW (type 3) relocation tells the loader "the 4 bytes at this RVA hold an
absolute address inside this image; add (actual_base - ImageBase) to them".
If the referenced 4 bytes are *not* an address -- for example, they are 0x90
code padding left behind by an earlier patch that shrank/moved code -- then the
loader still adds the delta and rewrites code bytes on the way in.

On Windows a DLL whose preferred base happens to be free is often loaded at that
base, so delta == 0 and every relocation is a no-op: the stale entries stay
invisible. Under Wine/Box86 on Android the module lands somewhere else, the
delta is applied, and the padding bytes are corrupted.

Concrete case (BeiDouSetItemCompat.dll, 2026-09-24):
  rva 0x1edc held `90 90 90 90`; delta 0x12a80000 turned it into `90 90 38 a3`.
  rva 0x1edf is a live branch target (`jmp 0x65c81edf` from .data+0x1f3), so the
  CPU executed `a3 90 90 90 90` = `mov dword ptr [0x90909090], eax` and died
  with an access violation writing 0x90909090 -- exactly the phone black screen.

Rule applied
------------
A base relocation carries an address *difference* that the loader adds to, so it
is only meaningful when the referenced DWORD is one of:

  ok            an address inside this image          -> keep
  zero          a null field                           -> keep
  displacement  ``A - S`` where ``A`` is an address in this image and ``S`` is
                an address inside a module pinned at a fixed base (for this
                client: BeiDou.exe at 0x400000).  The delta belongs to this
                DLL, and adding it to the difference is exactly right because
                ``S`` never moves.                       -> keep
  stale         none of the above: fill bytes, or a dead value left by an
                earlier ImageBase / earlier code layout -> strip

Only ``stale`` entries are ever removed, and only from an executable section.
``displacement`` is the trap this tool originally fell into: the value looks
"out of image" but is load-bearing.  See the worked example below.

Worked real case (BeiDouDamageSkinCompat.dll, 2026-09-24)
--------------------------------------------------------
RVA 0x1196 holds ``02 93 a4 6f`` (0x6fa49302), which is neither in-image nor
null, yet it is *required*.  The DLL's own shellcode writes a ``E9 <rel32>`` at
BeiDou.exe+0x37D0F to jump into itself:

    0x6fa49302 = (0x6fe80000 + 0x1016) - (0x4037d0f + 5)
                 \___ own image ___/   \_ pinned EXE _/

At the preferred base that lands on the DLL's own ``.text+0x1016``; under Wine
(base 0x785f0000, delta 0x08770000) the relocated value 0x781b9302 lands on
0x785f0000+0x1016 -- still correct.  Stripping this entry would make the jump
target 0x6fe81016, an unmapped address: a guaranteed crash on Android while
Windows (delta 0) keeps working.  Never strip a ``displacement``.

Usage
-----
    python3 fix_dll_reloc_hygiene.py <dll> [--apply] [--quiet]
    python3 fix_dll_reloc_hygiene.py clien/*.dll          # report only
    python3 fix_dll_reloc_hygiene.py <dll> --host 0x400000:0xE10000

--host lo:span (repeatable) declares a pinned module, i.e. a module whose base
never changes, used to recognise ``displacement`` values.  The default is
BeiDou.exe (ImageBase 0x400000, SizeOfImage 0xA94000).

Without --apply the tool only reports. With --apply it rewrites the .reloc
section, zeroes the leftover raw tail, updates the section VirtualSize and the
data-directory size, and recomputes the PE checksum. File length never changes.
The tool is idempotent: a clean DLL is reported as already clean and is not
rewritten.  Entries in a non-executable section are reported but never stripped
unless --force is also given.
"""
import struct
import sys
import os

IMAGE_REL_BASED_ABSOLUTE = 0
IMAGE_REL_BASED_HIGHLOW = 3
CHECKSUM_ALGO_NAME = "PE32 IMAGE_CHECKSUM"
IMAGE_SCN_MEM_EXECUTE = 0x20000000

# Pinned modules: base never changes between Windows and Wine/Box86, so a value
# stored as (in-image address) - (address inside a pinned module) stays correct
# under any delta.  BeiDou.exe is linked at 0x400000 with SizeOfImage 0xA94000.
DEFAULT_HOSTS = [(0x00400000, 0x00EA4000)]


def read_pe(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE file")
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    dd = opt + 96
    info = {
        "pe": pe,
        "opt": opt,
        "nsec": nsec,
        "sectab": pe + 24 + optsz,
        "image_base": struct.unpack_from("<I", data, opt + 28)[0],
        "size_of_image": struct.unpack_from("<I", data, opt + 56)[0],
        "checksum_off": opt + 64,
        "dd": dd,
        "sections": [],
    }
    for i in range(nsec):
        h = info["sectab"] + i * 40
        name = data[h:h + 8].rstrip(b"\0").decode("latin1")
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, h + 8)
        info["sections"].append(
            {"hdr": h, "name": name, "vsize": vsize, "va": va,
             "rsize": rsize, "raw": raw})
    rel_rva, rel_size = struct.unpack_from("<II", data, dd + 5 * 8)
    info["reloc_rva"] = rel_rva
    info["reloc_size"] = rel_size
    return info


def section_for(info, rva):
    for s in info["sections"]:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["rsize"]):
            return s
    return None


def rva_to_off(info, rva, need_raw=False):
    s = section_for(info, rva)
    if s is None:
        return None
    if need_raw and rva - s["va"] >= s["rsize"]:
        return None
    return s["raw"] + (rva - s["va"])


def parse_relocs(data, info):
    """-> (blocks, entries) where blocks keeps the raw page/prefix order."""
    off = rva_to_off(info, info["reloc_rva"])
    if off is None or not info["reloc_size"]:
        return [], []
    end = off + info["reloc_size"]
    blocks, entries = [], []
    while off + 8 <= end:
        page, block_size = struct.unpack_from("<II", data, off)
        if block_size < 8 or off + block_size > end:
            break
        words = []
        for i in range((block_size - 8) // 2):
            w = struct.unpack_from("<H", data, off + 8 + i * 2)[0]
            words.append(w)
            if w >> 12:
                entries.append({"rva": page + (w & 0xFFF), "type": w >> 12,
                                "word": w})
        blocks.append({"page": page, "words": words})
        off += block_size
    return blocks, entries


def pe_checksum(data, checksum_off):
    buf = bytearray(data)
    struct.pack_into("<I", buf, checksum_off, 0)
    acc = 0
    for i in range(0, len(buf), 4):
        acc += int.from_bytes(buf[i:i + 4].ljust(4, b"\0"), "little")
        acc = (acc & 0xFFFFFFFF) + (acc >> 32)
    acc = (acc & 0xFFFF) + (acc >> 16)
    acc = (acc & 0xFFFF) + (acc >> 16)
    return ((acc & 0xFFFF) + len(data)) & 0xFFFFFFFF


def section_chars(data, section):
    return struct.unpack_from("<I", data, section["hdr"] + 36)[0]


def displacement_site(value, lo, hi, hosts):
    """If ``value`` can be read as ``A - S`` (A in this image, S in a pinned
    module), return ((site_lo, site_hi), (rva_lo, rva_hi)); else None.

    We need some S in [hlo, hlo+hlen) with ``(value + S) mod 2^32`` in [lo, hi).
    That is equivalent to S in [lo-value, hi-value) modulo 2^32, so intersect
    that (image-span-sized) interval with each host range, allowing the
    +-2^32 wrap.  The exact site inside the intersection is not recoverable
    statically, so report the range instead of inventing a single address.
    """
    for hlo, hlen in hosts:
        for k in (-0x100000000, 0, 0x100000000):
            a = max(lo - value, hlo + k)
            b = min(hi - value, hlo + hlen + k)
            if a < b:
                sites = (a & 0xFFFFFFFF, b & 0xFFFFFFFF)
                rvas = ((value + a) & 0xFFFFFFFF) - lo, ((value + b) & 0xFFFFFFFF) - lo
                return sites, rvas
    return None


def classify(data, info, entry, hosts=None):
    """-> (verdict, detail) verdict in {ok, zero, displacement, stale}"""
    hosts = DEFAULT_HOSTS if hosts is None else hosts
    off = rva_to_off(info, entry["rva"])
    if off is None or off + 4 > len(data):
        return "stale", {"reason": "rva outside file", "bytes": b""}
    raw = bytes(data[off:off + 4])
    value = struct.unpack("<I", raw)[0]
    lo = info["image_base"]
    hi = lo + info["size_of_image"]
    section = section_for(info, entry["rva"])
    exec_sec = bool(section and section_chars(data, section) & IMAGE_SCN_MEM_EXECUTE)
    base = {"value": value, "bytes": raw, "exec": exec_sec,
            "section": section["name"] if section else "?"}
    if value == 0:
        return "zero", base
    if lo <= value < hi:
        return "ok", base
    hit = displacement_site(value, lo, hi, hosts)
    if hit:
        base["sites"], base["rvas"] = hit
        return "displacement", base
    return "stale", base


def disasm_context(data, info, rva, pad=8):
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except Exception:
        return ""
    off = rva_to_off(info, rva)
    if off is None:
        return ""
    start = max(0, off - pad)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    out = []
    first_addr = info["image_base"] + rva - (off - start)
    for ins in md.disasm(bytes(data[start:off + pad]), first_addr):
        mark = "*" if ins.address == info["image_base"] + rva else " "
        out.append(f"{mark}{ins.mnemonic} {ins.op_str}".strip())
    return " | ".join(out)


def rebuild_relocs(blocks, info, drop_rvas, data):
    """Drop entries and re-emit the block chain, 4-byte aligned per block."""
    drop = set(drop_rvas)
    out = bytearray()
    for blk in blocks:
        words = [w for w in blk["words"]
                 if not ((w >> 12) and (blk["page"] + (w & 0xFFF)) in drop)]
        body = bytearray()
        for w in words:
            body += struct.pack("<H", w)
        while len(body) % 4:
            body += struct.pack("<H", IMAGE_REL_BASED_ABSOLUTE)
        block_size = 8 + len(body)
        out += struct.pack("<II", blk["page"], block_size) + body
    while len(out) % 4:
        out += struct.pack("<H", IMAGE_REL_BASED_ABSOLUTE)
    return bytes(out)


def simulate_relocations(data, info, probe_delta):
    """Apply all relocations with a probe delta; return the relocated image."""
    _, entries = parse_relocs(data, info)
    img = bytearray(data)
    for e in entries:
        off = rva_to_off(info, e["rva"])
        if off is None or off + 4 > len(img):
            continue
        v = struct.unpack_from("<I", img, off)[0]
        struct.pack_into("<I", img, off, (v + probe_delta) & 0xFFFFFFFF)
    return bytes(img)


def parse_hosts(argv):
    hosts = []
    for i, a in enumerate(argv):
        if a == "--host" and i + 1 < len(argv):
            spec = argv[i + 1]
        elif a.startswith("--host="):
            spec = a.split("=", 1)[1]
        else:
            continue
        lo_s, _, span_s = spec.partition(":")
        lo = int(lo_s, 0)
        span = int(span_s, 0)
        hosts.append((lo, lo + span))
    return hosts or DEFAULT_HOSTS


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    apply_fix = "--apply" in sys.argv
    quiet = "--quiet" in sys.argv
    force = "--force" in sys.argv
    hosts = parse_hosts(sys.argv[1:])
    if not args:
        print(__doc__)
        return 2
    rc = 0
    for path in args:
        rc |= process(path, apply_fix, quiet, hosts, force)
    return rc


def process(path, apply_fix, quiet, hosts=None, force=False):
    hosts = DEFAULT_HOSTS if hosts is None else hosts
    data = bytearray(open(path, "rb").read())
    info = read_pe(data)
    rel_sec = section_for(info, info["reloc_rva"]) if info["reloc_size"] else None
    if rel_sec is None or rel_sec["name"] != ".reloc":
        print(f"[skip] {path}: no .reloc directory")
        return 0
    blocks, entries = parse_relocs(data, info)
    doomed, kept_disp, kept_nonexec, zeroed = [], [], [], []
    for e in entries:
        verdict, detail = classify(data, info, e, hosts)
        if verdict == "stale":
            (doomed if detail["exec"] or force else kept_nonexec).append((e, detail))
        elif verdict == "displacement":
            kept_disp.append((e, detail))
        elif verdict == "zero":
            zeroed.append((e, detail))

    reloc_summary = (f"{len(entries)} relocations, "
                     f"{len(kept_disp)} cross-module displacement(s) kept")
    for e, d in (kept_disp if not quiet else []):
        (slo, shi), (rlo, rhi) = d["sites"], d["rvas"]
        print(f"    KEEP RVA {e['rva']:#08x} sec={d['section']} value={d['value']:#010x}"
              f" = (image + {rlo:#x}..{rhi:#x}) - (host {slo:#x}..{shi:#x})"
              f"   [cross-module displacement; stripping it breaks rebasing]")
    if not doomed:
        if kept_nonexec and not quiet:
            print(f"[review] {os.path.basename(path)}: {len(kept_nonexec)} entry(ies) "
                  f"in a non-executable section look stale but were kept")
            for e, d in kept_nonexec:
                print(f"    RVA {e['rva']:#08x} sec={d['section']} "
                      f"bytes={d['bytes'].hex()} value={d['value']:#010x}")
        print(f"[clean] {os.path.basename(path)}: {reloc_summary}; nothing to do")
        return 0

    print(f"[found] {os.path.basename(path)}: {len(doomed)} stale of "
          f"{len(entries)} relocations (image {info['image_base']:#x}+"
          f"{info['size_of_image']:#x})")
    for e, d in doomed:
        ctx = disasm_context(data, info, e["rva"])
        print(f"    RVA {e['rva']:#08x}  bytes={d['bytes'].hex()}"
              f"  value={d.get('value', 0):#010x}"
              + (f"   ctx: {ctx}" if ctx and not quiet else ""))
    if zeroed and not quiet:
        print(f"    note: {len(zeroed)} entr(ies) point at a null field, kept as-is")
    if not apply_fix:
        print("    (report only; re-run with --apply to strip them)")
        return 0

    drop = [e["rva"] for e, _ in doomed]
    kept_rvas = {e["rva"] for e, _ in kept_disp + kept_nonexec}
    # --- prove the rewrite is safe: the dropped bytes must be pure padding,
    #     i.e. untouched by a probe relocation afterwards ---
    before = simulate_relocations(data, info, 0x12340000)
    new_reloc = rebuild_relocs(blocks, info, drop, data)
    off = rva_to_off(info, info["reloc_rva"])
    raw_size = rel_sec["rsize"]
    if len(new_reloc) > raw_size:
        print(f"[fail] {path}: rebuilt .reloc ({len(new_reloc)}) exceeds raw size")
        return 1
    struct.pack_into("<II", data, info["dd"] + 5 * 8, info["reloc_rva"],
                     len(new_reloc))
    struct.pack_into("<I", data, rel_sec["hdr"] + 8, len(new_reloc))
    data[off:off + len(new_reloc)] = new_reloc
    data[off + len(new_reloc):off + raw_size] = b"\x00" * (raw_size - len(new_reloc))
    struct.pack_into("<I", data, info["checksum_off"], 0)
    struct.pack_into("<I", data, info["checksum_off"], pe_checksum(data, info["checksum_off"]))

    after = simulate_relocations(data, info, 0x12340000)
    for rva in drop:
        o = rva_to_off(info, rva)
        stable = bytes(data[o:o + 4])
        print(f"    RVA {rva:#08x}: would-relocate {before[o:o + 4].hex()} "
              f"-> stays {stable.hex()}")
        if after[o:o + 4] != stable:
            print(f"[fail] {path}: relocation still mutates RVA {rva:#x}")
            return 1
    _, left = parse_relocs(data, info)
    bad = [e for e in left
           if classify(data, info, e, hosts)[0] == "stale" and e["rva"] not in kept_rvas]
    if bad:
        print(f"[fail] {path}: {len(bad)} stale relocations remain")
        return 1
    open(path, "wb").write(bytes(data))
    print(f"[fixed] {path}: {len(doomed)} stale relocations removed, "
          f"{len(kept_disp)} displacement(s) preserved, "
          f".reloc {info['reloc_size']:#x} -> {len(new_reloc):#x}, "
          f"checksum {pe_checksum(data, info['checksum_off']):#x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
