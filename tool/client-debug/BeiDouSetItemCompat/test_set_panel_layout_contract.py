"""Instruction boundaries, base-relative helpers and unchanged native lifetime."""
import os
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from fix_dll_reloc_hygiene import read_pe, parse_relocs, rva_to_off
from set_panel_patch import (build_helpers, CAVE_RAW, CAVE_RVA, LAYOUT_WINDOWS, DRAW_SITES,
                             RETAINED_RELOCS)

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../../clien/BeiDouSetItemCompat.dll')
data = open(path, 'rb').read()
baseline = open(os.path.join(HERE, 'backup/BeiDouSetItemCompat.dll.before-stat-labels'), 'rb').read()
info = read_pe(data)
image = info['image_base']
code, symbols = build_helpers()
assert data[CAVE_RAW:CAVE_RAW + len(code)] == code
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.detail = True


def instructions(blob, start, length):
    offset = rva_to_off(info, start)
    return list(md.disasm(blob[offset:offset + length], image + start))


baseline_boundaries = set()
for start, end in ((0x21b6, 0x262f), (0x2b4e, 0x3796)):
    for instruction in instructions(baseline, start, end - start):
        baseline_boundaries.add(instruction.address - image)
        if instruction.mnemonic.startswith('j') or instruction.mnemonic == 'call':
            operand = instruction.operands[0]
            if operand.type == 2:
                target = operand.imm - image
                assert not any(lo < target < hi for lo, hi in LAYOUT_WINDOWS), (hex(target), instruction)
for lo, hi in LAYOUT_WINDOWS:
    assert lo in baseline_boundaries and hi in baseline_boundaries, (hex(lo), hex(hi))

calls = {0x2b54: 'allocate_frame', 0x23df: 'save_slot', 0x2451: 'store_slot',
         0x3012: 'save_widget', 0x306d: 'collect_panel', 0x30d8: 'size_panel',
         0x3237: 'select_slot', 0x3063: 'position_panel', 0x3749: 'position_panel'}
calls.update({site: 'draw_column' for site in DRAW_SITES})
calls.update({site: 'make_dark_layer' for site in (0x2b90, 0x2d27, 0x312c)})
calls[0x31bd] = 'format_title'
helper_boundaries = {ins.address - image for ins in md.disasm(code, image + CAVE_RVA)}
for rva, name in calls.items():
    instruction = instructions(data, rva, 5)[0]
    assert instruction.mnemonic == ('jmp' if name == 'select_slot' else 'call')
    assert instruction.operands[0].imm - image == symbols[name]
    assert symbols[name] in helper_boundaries
for instruction in md.disasm(code, image + CAVE_RVA):
    if instruction.mnemonic.startswith('j') or instruction.mnemonic == 'call':
        if instruction.operands[0].type == 2:
            assert instruction.operands[0].imm - image in helper_boundaries, instruction

for rva in (0x307a, 0x322b):
    instruction = instructions(data, rva, 6)[0]
    assert instruction.operands[1].mem.disp == -0x1010
assert instructions(data, 0x322b, 6)[0].bytes[0] == 0x3b
for rva, length in ((0x1b7f, 0x5d), (0x1c46, 0x40), (0x2457, 12),
                    (0x2a75, 0xd9), (0x3786, 0x10), (0x198e, 0x80)):
    offset = rva_to_off(info, rva)
    assert data[offset:offset + length] == baseline[offset:offset + length], hex(rva)
_, entries = parse_relocs(data, info)
assert len(entries) == 361
for entry in entries:
    assert entry['rva'] in RETAINED_RELOCS or not any(lo <= entry['rva'] < hi for lo, hi in LAYOUT_WINDOWS)
    assert not CAVE_RVA <= entry['rva'] < CAVE_RVA + len(code)
assert RETAINED_RELOCS.issubset({entry['rva'] for entry in entries})
print('set panel layout instruction/lifetime contract OK', len(code), 'helper bytes')
