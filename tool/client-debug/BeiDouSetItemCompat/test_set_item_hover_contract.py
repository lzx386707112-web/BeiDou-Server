#!/usr/bin/env python3
"""Execute the native packet decoder and hover lookup on Java packet fixtures.

Run with a directory exported by SetItemPacketTest's setItemPacketFixtureDirectory.
Executes matching, slot aggregation, tier text, wrapping and placement. COM/font
boundaries are mocked; this is not evidence of a real client launch or pixels.
"""
import glob
import os
import struct
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_EDI, UC_X86_REG_ESI, UC_X86_REG_ESP,
    UC_X86_REG_EIP,
)

from fix_dll_reloc_hygiene import read_pe, parse_relocs, rva_to_off

HERE = os.path.dirname(os.path.abspath(__file__))
DLL = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, '../../../clien/BeiDouSetItemCompat.dll')
data = open(DLL, 'rb').read()
info = read_pe(data)
_, relocations = parse_relocs(data, info)
fixtures = glob.glob(os.path.join(sys.argv[1], '*.packet'))
assert len(fixtures) == 5, fixtures


def dword(cpu, address):
    return struct.unpack('<I', cpu.mem_read(address, 4))[0]


def ansi(cpu, address):
    return bytes(cpu.mem_read(address, 96)).split(b'\0', 1)[0].decode('gbk')


def wide(cpu, address):
    value = bytearray()
    while True:
        char = bytes(cpu.mem_read(address + len(value), 2))
        if char == b'\0\0':
            return value.decode('utf-16-le')
        value.extend(char)


for image in (info['image_base'], 0x78700000):
    cpu = Uc(UC_ARCH_X86, UC_MODE_32)
    cpu.mem_map(image, info['size_of_image'])
    for section in info['sections']:
        cpu.mem_write(image + section['va'], data[section['raw']:section['raw'] + section['rsize']])
    for entry in relocations:
        rva = entry['rva']
        value = struct.unpack_from('<I', data, rva_to_off(info, rva))[0]
        cpu.mem_write(image + rva, struct.pack('<I', (value + image - info['image_base']) & 0xffffffff))
    stack, buffer, native = 0x02000000, 0x03000000, 0x04000000
    cpu.mem_map(stack, 0x10000)
    cpu.mem_map(buffer, 0x10000)
    cpu.mem_map(native, 0x1000)
    cpu.mem_write(native + 0x100, b'\xc2\x0c\x00')
    cpu.mem_write(image + 0x3100f8, struct.pack('<I', native + 0x100))
    for rva, offset in ((0x310118, 0x200), (0x3100f4, 0x300), (0x310114, 0x400)):
        cpu.mem_write(image + rva, struct.pack('<I', native + offset))
    cpu.mem_write(image + 0xa894, struct.pack('<I', native + 0x500))
    cpu.mem_write(image + 0xa898, struct.pack('<I', native + 0x600))
    ebp, esp = stack + 0x8000, stack + 0x7000
    mode = ['decode']
    outcome = []
    drawn, positions, lifecycle = [], [], []
    fonts, drawn_colors, backgrounds = {}, [], []

    def return_call(emulator, result=0, cleanup=0):
        current = emulator.reg_read(UC_X86_REG_ESP)
        target = dword(emulator, current)
        emulator.reg_write(UC_X86_REG_EAX, result)
        emulator.reg_write(UC_X86_REG_ESP, current + 4 + cleanup)
        emulator.reg_write(UC_X86_REG_EIP, target)

    def put(address, value):
        cpu.mem_write(address, struct.pack('<I', value))

    def visit(emulator, address, size, user_data):
        if address not in watched:
            return
        current = emulator.reg_read(UC_X86_REG_ESP)
        eax, ecx, edx = (emulator.reg_read(r) for r in
                         (UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EDX))
        if address == native + 0x100:
            current = emulator.reg_read(UC_X86_REG_ESP)
            dest, source, capacity = struct.unpack('<III', emulator.mem_read(current + 4, 12))
            copied = bytes(emulator.mem_read(source, capacity)).split(b'\0', 1)[0][:capacity - 1]
            emulator.mem_write(dest, copied + b'\0')
            emulator.reg_write(UC_X86_REG_EAX, dest)
        elif address == native + 0x200:
            dest, fmt = dword(emulator, current + 4), wide(emulator, dword(emulator, current + 8))
            cursor, text = current + 12, ''
            index = 0
            while index < len(fmt):
                if fmt[index] != '%':
                    text += fmt[index]
                    index += 1
                    continue
                token = fmt[index + 1]
                value = dword(emulator, cursor)
                text += wide(emulator, value) if token == 's' else str(value)
                cursor += 4
                index += 2
            emulator.mem_write(dest, text.encode('utf-16-le') + b'\0\0')
            return_call(emulator, len(text))
        elif address == native + 0x300:
            left, right = (ansi(emulator, dword(emulator, current + off)) for off in (4, 8))
            return_call(emulator, 0 if left == right else 1, 8)
        elif mode[0] == 'render':
            if address == image + 0x290b:
                font = native + 0x800 + (eax - image - 0x8860) * 4
                fonts[font] = edx
                put(eax, font)
                return_call(emulator, 1)
            elif address == native + 0x500:
                backgrounds.append(dword(emulator, current + 28))
                put(dword(emulator, current + 4), native + 0x900)
                put(image + 0x8890, native + 0xa00)
                lifecycle.append('create')
                return_call(emulator, native + 0x900, 28)
            elif address == native + 0x600:
                lifecycle.append('clear')
                return_call(emulator)
            elif address == image + 0x1203:
                return_call(emulator, native + 0xb00)
            elif address in (image + 0x119a, image + 0x11d9, image + 0x153d, native + 0x400):
                if address == native + 0x400:
                    emulator.mem_write(dword(emulator, current + 4), b'log\0')
                return_call(emulator)
            elif address == image + 0x1c86:
                text = ansi(emulator, eax)[:ecx - 1]
                emulator.mem_write(edx, text.encode('utf-16-le') + b'\0\0')
                return_call(emulator)
            elif address == image + 0x11b9:
                return_call(emulator, sum(11 if ord(char) > 127 else 6 for char in wide(emulator, eax)))
            elif address == image + 0x111e:
                return_call(emulator, int(ansi(emulator, edx) in ansi(emulator, eax)))
            elif address == image + 0x174d:
                drawn.append((ecx, dword(emulator, current + 4), wide(emulator, dword(emulator, current + 8))))
                drawn_colors.append(fonts[edx])
                return_call(emulator)
            elif address == image + 0x1b07:
                positions.append(('star' if eax == native + 0xf00 else 'primary', edx, ecx))
                return_call(emulator)
            elif address == image + 0x2a75:
                positions.append(('set', ecx, dword(emulator, current + 4)))
                return_call(emulator)
            elif address == image + 0x3786:
                outcome.append('rendered')
                emulator.emu_stop()
        # Stop immediately after decoding, before diagnostic formatting/UI dispatch.
        if mode[0] == 'decode' and address == image + 0x262f:
            assert emulator.mem_read(ebp - 0x140, 1) == b'\x01', 'decoder rejected fixture'
            outcome.append('decoded')
            emulator.emu_stop()
        elif mode[0] == 'lookup' and address in (image + 0x2f76, image + 0x3008):
            # First matching item, before native font/Canvas creation.
            outcome.append('matched' if address == image + 0x2f76 else 'missing')
            emulator.emu_stop()

    watched = {image + rva for rva in (0x262f, 0x2f76, 0x3008, 0x290b, 0x1203, 0x119a,
                                      0x11d9, 0x153d, 0x1c86, 0x11b9, 0x111e, 0x174d,
                                      0x1b07, 0x2a75, 0x3786)} | {
        native + offset for offset in (0x100, 0x200, 0x300, 0x400, 0x500, 0x600)}
    cpu.hook_add(UC_HOOK_CODE, visit)
    for fixture in fixtures:
        packet = open(fixture, 'rb').read()
        cpu.mem_write(buffer, packet)
        cpu.mem_write(stack, b'\0' * 0x10000)
        cpu.mem_write(ebp - 0x15c, struct.pack('<I', native))
        for register, value in ((UC_X86_REG_EBP, ebp), (UC_X86_REG_ESP, esp),
                                (UC_X86_REG_ESI, buffer), (UC_X86_REG_EAX, len(packet)),
                                (UC_X86_REG_EBX, 0), (UC_X86_REG_ECX, 0x17a)):
            cpu.reg_write(register, value)
        mode[0] = 'decode'
        try:
            cpu.emu_start(image + 0x21b6, image + 0x262f + 1, count=20_000_000)
        except Exception:
            print('decoder stopped at', hex(cpu.reg_read(UC_X86_REG_EIP)),
                  'cursor', dword(cpu, ebp - 0x144), 'valid', bytes(cpu.mem_read(ebp - 0x140, 1)))
            raise
        assert outcome.pop() == 'decoded'
        assert dword(cpu, ebp - 0x144) == len(packet) - 2, 'decoder did not consume all set data'
        count = dword(cpu, ebp - 0x168)
        assert 0 < count <= 96
        # The original dispatch publishes the decoded count after the log call.
        cpu.mem_write(image + 0xa8b0, struct.pack('<I', count))
        cpu.mem_write(image + 0x18c9c0, bytes(cpu.mem_read(image + 0xa8c0, 0x182100)))
        candidates = set()
        for view in range(count):
            address = image + 0xa8c0 + view * 0x4058
            slots = dword(cpu, address + 0x68)
            assert slots <= 8
            for slot in range(slots):
                start = address + slot * 0x554
                alternatives = dword(cpu, start + 0x6c)
                assert alternatives <= 10
                for alt in range(alternatives):
                    candidates.add(dword(cpu, start + 0x70 + alt * 0x88))
        assert 1302258 in candidates
        mode[0] = 'lookup'
        for item in sorted(candidates) + [1999999]:
            cpu.mem_write(image + 0x4008, struct.pack('<I', item))
            cpu.reg_write(UC_X86_REG_EBP, ebp)
            cpu.reg_write(UC_X86_REG_ESP, esp)
            cpu.emu_start(image + 0x2eff, image + 0x3009, count=100_000)
            assert outcome.pop() == ('matched' if item in candidates else 'missing'), item
        # One representative per set plus all Ultimate alternatives, including slot 11.
        expected, representatives = {}, set()
        for view in range(count):
            panel = image + 0x18c9c0 + view * 0x4058
            set_id = dword(cpu, panel)
            expected.setdefault(set_id, {})
            for slot in range(dword(cpu, panel + 0x68)):
                row = panel + slot * 0x554
                for alt in range(dword(cpu, row + 0x6c)):
                    record = row + 0x70 + alt * 0x88
                    item = dword(cpu, record)
                    key = int.from_bytes(cpu.mem_read(record + 0x86, 2), 'little')
                    assert key > 0, 'slot identity was not decoded'
                    expected[set_id].setdefault(key, []).append((item, ansi(cpu, record + 5)))
                    if slot == 0 and alt == 0 or set_id == 10030:
                        representatives.add(item)
        # Every emitted row must appear, including all effect tiers, in both load bases.
        for item in sorted(representatives):
            render_esp = ebp - 0x140c
            put(image + 0x4008, item)
            cpu.mem_write(stack, b'\0' * 0x10000)
            put(ebp - 0x3b4, native + 0xc00)
            put(native + 0xc08, 220)
            put(native + 0xc0c, 260)
            put(native + 0xc10, native + 0xd00)
            put(ebp - 0x3bc, 260)
            put(ebp + 0xc, 700)
            put(ebp + 0x10, 550)
            cpu.mem_write(image + 0x8875, b'\x01')
            cpu.mem_write(image + 0x8874, b'\x00')
            drawn.clear()
            drawn_colors.clear()
            backgrounds.clear()
            positions.clear()
            lifecycle.clear()
            mode[0] = 'render'
            cpu.reg_write(UC_X86_REG_EBP, ebp)
            cpu.reg_write(UC_X86_REG_ESP, render_esp)
            cpu.emu_start(image + 0x2eff, image + 0x3787, count=1_000_000)
            assert outcome.pop() == 'rendered'
            assert cpu.reg_read(UC_X86_REG_ESP) == render_esp, 'render stack drift'
            panel = image + 0x18c9c0 + cpu.reg_read(UC_X86_REG_EDI)
            set_id = dword(cpu, panel)
            slots = expected[set_id]
            assert dword(cpu, ebp - 0x1010) == len(slots), (item, set_id, len(slots))
            assert len(drawn) == 2 + 2 * len(slots) + sum(
                1 + dword(cpu, panel + 0x2b14 + tier * 0x2a8)
                for tier in range(dword(cpu, panel + 0x2b0c))), (set_id, drawn)
            assert backgrounds == [0xff1e1e1e]
            assert drawn[0][2].startswith(ansi(cpu, panel + 4) + '套装 (')
            for (_, _, text), color in zip(drawn, drawn_colors):
                if text.endswith('件套效果') or text == '套装效果' or text == drawn[0][2]:
                    assert color == 0xffa8ff53, (text, hex(color))
                elif ' +' in text:
                    assert color == 0xffcbcfd7, (text, hex(color))
            for tier in range(dword(cpu, panel + 0x2b0c)):
                required = dword(cpu, panel + 0x2b10 + tier * 0x2a8)
                assert f'{required}件套效果' in [text for _, _, text in drawn]
            width, height = dword(cpu, image + 0x888c), dword(cpu, image + 0x8888)
            assert width <= 472 and height <= 476, (set_id, width, height)
            assert all(0 <= x < width and 0 <= y < height - 12 for x, y, _ in drawn), (set_id, drawn)
            assert positions == [('primary', 799 - 260 - 4 - width, 599 - max(220, height)),
                                 ('set', 799 - width, 599 - max(220, height))], positions
            if set_id == 10030:
                assert len(slots) == 11
                texts = [text for _, _, text in drawn]
                for alternatives in slots.values():
                    selected = next((name for candidate, name in alternatives if candidate == item), alternatives[0][1])
                    assert selected in texts, (item, selected, texts)
                assert width == 472 and any(x >= 236 for x, _, _ in drawn)
            # Repeat hover repositions both panels without rebuilding or redrawing.
            drawn.clear()
            lifecycle.clear()
            put(ebp - 0x3b4, native + 0xc00)
            put(ebp - 0x3bc, 260)
            cpu.reg_write(UC_X86_REG_ESP, render_esp)
            cpu.emu_start(image + 0x2eff, image + 0x3787, count=100_000)
            assert outcome.pop() == 'rendered'
            assert not drawn and not lifecycle, (item, lifecycle)
            if item == 1302258:
                positions.clear()
                cpu.mem_write(image + 0x6854, b'\x01')
                put(image + 0x6868, 27)
                put(image + 0x6870, native + 0xf00)
                put(ebp + 0xc, 0)
                put(ebp + 0x10, 0)
                put(ebp - 0x3b4, native + 0xc00)
                put(ebp - 0x3bc, 260)
                cpu.reg_write(UC_X86_REG_ESP, render_esp)
                cpu.emu_start(image + 0x2eff, image + 0x3787, count=100_000)
                assert outcome.pop() == 'rendered'
                assert positions == [('primary', 0, 27), ('star', 0, 0), ('set', 264, 27)], positions
                assert not drawn and not lifecycle
                cpu.mem_write(image + 0x6854, b'\x00')
        print(os.path.basename(fixture), 'native decode/hover/full-layout OK', count, 'views', len(candidates),
              'items', len(representatives), 'render cases', hex(image), flush=True)
    # Execute the expanded-frame prologue and its stack-page probe, not just a synthetic frame.
    mode[0] = 'render'
    # Native clear on leaving the item still destroys the tooltip and resets its cache.
    lifecycle.clear()
    put(render_esp - 4, native + 0xe00)
    cpu.reg_write(UC_X86_REG_ESP, render_esp - 4)
    cpu.emu_start(image + 0x1b7f, native + 0xe00, count=1000)
    assert lifecycle == ['clear']
    assert cpu.mem_read(image + 0x8874, 1) == b'\x00'
    assert dword(cpu, image + 0x4004) == 0xffffffff

    # Distinct slots of the same category must not collapse; later alternative
    # fragments select an equipped candidate ahead of the hovered candidate.
    cpu.mem_write(image + 0x18c9c0, b'\0' * (3 * 0x4058))
    put(image + 0xa8b0, 3)
    for view, keys in enumerate((range(1, 9), range(9, 13), [12])):
        panel = image + 0x18c9c0 + view * 0x4058
        put(panel, 9999)
        put(panel + 0x68, len(keys))
        for index, key in enumerate(keys):
            row = panel + index * 0x554
            put(row + 0x6c, 1)
            record = row + 0x70
            put(record, 1002000 + key if key < 12 else (1302258 if view == 1 else 1302000))
            cpu.mem_write(record + 0x86, struct.pack('<H', key))
            if view == 2:
                cpu.mem_write(record + 4, b'\x01')
    put(ebp - 0x3b0, 1302258)
    cpu.reg_write(UC_X86_REG_EDI, 0x4058)
    cpu.reg_write(UC_X86_REG_ESP, render_esp)
    cpu.emu_start(image + 0x306d, image + 0x3072, count=100_000)
    assert dword(cpu, ebp - 0x1010) == 12
    selected = [dword(cpu, ebp - 0x1000 + index * 4) for index in range(12)]
    assert [int.from_bytes(cpu.mem_read(record + 0x86, 2), 'little') for record in selected] == list(range(1, 13))
    assert dword(cpu, selected[-1]) == 1302000

    # Invalid metadata must never write past the fixed 768-pointer scratch area.
    cpu.mem_write(image + 0x18c9c0, b'\0' * (11 * 0x4058))
    put(image + 0xa8b0, 11)
    for view in range(11):
        panel = image + 0x18c9c0 + view * 0x4058
        put(panel, 9999)
        put(panel + 0x68, 8)
        for slot in range(8):
            row = panel + slot * 0x554
            put(row + 0x6c, 10)
            for alt in range(10):
                record = row + 0x70 + alt * 0x88
                put(record, 1002000)
                cpu.mem_write(record + 0x86, struct.pack('<H', view * 80 + slot * 10 + alt + 1))
    put(ebp - 0x400, 0x12345678)
    cpu.reg_write(UC_X86_REG_EDI, 0)
    cpu.reg_write(UC_X86_REG_ESP, render_esp)
    cpu.emu_start(image + 0x306d, image + 0x3072, count=5_000_000)
    assert dword(cpu, ebp - 0x1010) == 768
    assert dword(cpu, ebp - 0x400) == 0x12345678

    initial_esp = stack + 0x9000
    cpu.reg_write(UC_X86_REG_ESP, initial_esp)
    cpu.emu_start(image + 0x2b4e, image + 0x2b5a, count=100)
    assert cpu.reg_read(UC_X86_REG_EBP) == initial_esp - 4
    assert cpu.reg_read(UC_X86_REG_ESP) == initial_esp - 16 - 0x1400
print('native set item hover contract OK')
