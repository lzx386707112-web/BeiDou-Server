"""Execute MakeLayer ARGB arguments and title suffix selection at both load bases."""
import hashlib
import os
import struct
import sys

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
                              UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI,
                              UC_X86_REG_EBP, UC_X86_REG_ESP)
from fix_dll_reloc_hygiene import read_pe, parse_relocs, rva_to_off
from set_panel_patch import LAYOUT_WINDOWS, STYLE_STRINGS_RAW

HERE = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../../clien/BeiDouSetItemCompat.dll')
data = open(path, 'rb').read()
previous = open(os.path.join(HERE, 'backup/BeiDouSetItemCompat.dll.before-panel-style'), 'rb').read()
assert hashlib.sha256(previous).hexdigest() == '2e3c10a33d5c095dea934ed77a2b77b43feb27016b2915031c244d0e8b7cab2d'
assert len(previous) == len(data) == 0x5a00
info = read_pe(data)
allowed = [(rva_to_off(info, lo), rva_to_off(info, hi)) for lo, hi in LAYOUT_WINDOWS]
allowed += [(info['checksum_off'], info['checksum_off'] + 4), (0x4600, 0x4a00),
            (0x5300, 0x5900), (STYLE_STRINGS_RAW, STYLE_STRINGS_RAW + 0x40),
            (info['dd'] + 44, info['dd'] + 48)]
reloc_section = next(section for section in info['sections'] if section['name'] == '.reloc')
allowed.append((reloc_section['hdr'] + 8, reloc_section['hdr'] + 12))
for offset, (old, new) in enumerate(zip(previous, data)):
    assert old == new or any(lo <= offset < hi for lo, hi in allowed), hex(offset)
assert data[0x4a00:0x52b2] == previous[0x4a00:0x52b2], 'title-series or stat labels changed'
_, relocations = parse_relocs(data, info)
exe = pefile.PE(os.path.join(HERE, '../../../clien/BeiDou.exe'))

# Both equipment paths collect basic text before creating their native layer.
disassembler = Cs(CS_ARCH_X86, CS_MODE_32)
for basic, layers in ((0x8e7b1c, (0x8e7e5e,)), (0x8e8e67, (0x8e97c3, 0x8e97e7))):
    for address, target in ((basic, 0x8eca0c), *((layer, 0x8f3141) for layer in layers)):
        instruction = next(disassembler.disasm(exe.get_data(address - 0x400000, 5), address))
        assert instruction.mnemonic == 'call' and instruction.op_str == hex(target)
    assert all(basic < layer for layer in layers)
basic_code = list(disassembler.disasm(exe.get_data(0x8eca0c - 0x400000, 0x5b9), 0x8eca0c))
assert not any(instruction.mnemonic == 'call' and instruction.op_str == '0x8f3141'
               for instruction in basic_code), 'basic tooltip unexpectedly creates its layer'
assert data[0x1af2 - 0xc00:0x1af7 - 0xc00] == bytes.fromhex('a3aca8c865')


def dword(cpu, address):
    return struct.unpack('<I', cpu.mem_read(address, 4))[0]


def wide(cpu, address):
    result = bytearray()
    while True:
        char = bytes(cpu.mem_read(address + len(result), 2))
        if char == b'\0\0':
            return result.decode('utf-16-le')
        result.extend(char)


for image in (info['image_base'], 0x78700000):
    cpu = Uc(UC_ARCH_X86, UC_MODE_32)
    cpu.mem_map(image, info['size_of_image'])
    for section in info['sections']:
        cpu.mem_write(image + section['va'], data[section['raw']:section['raw'] + section['rsize']])
    for entry in relocations:
        value = struct.unpack_from('<I', data, rva_to_off(info, entry['rva']))[0]
        cpu.mem_write(image + entry['rva'], struct.pack('<I', (value + image - info['image_base']) & 0xffffffff))
    stack, native = 0x02000000, 0x04000000
    cpu.mem_map(stack, 0x10000)
    cpu.mem_map(native, 0x10000)
    cpu.mem_map(0x8f3000, 0x1000)
    cpu.mem_write(0x8f3000, exe.get_data(0x8f3000 - exe.OPTIONAL_HEADER.ImageBase, 0x1000))
    cpu.mem_write(native + 0x100, b'\xc2\x1c\x00')
    cpu.mem_write(native + 0x3000, b'\xc2\x18\x00')

    def put(address, value):
        cpu.mem_write(address, struct.pack('<I', value))

    put(image + 0xa894, native + 0x100)
    put(image + 0xa8ac, native + 0x200)
    captures = []

    def visit(emulator, address, size, user_data):
        current = emulator.reg_read(UC_X86_REG_ESP)
        if address == native + 0x100:
            captures.append(tuple(struct.unpack('<7I', emulator.mem_read(current + 4, 28))))
            assert emulator.reg_read(UC_X86_REG_EAX) == 0x12345678, 'wrapper clobbered EAX'
            emulator.reg_write(UC_X86_REG_EAX, 0xabcdef)
        elif address == native + 0x3000:
            captures.append(tuple(struct.unpack('<6I', emulator.mem_read(current + 4, 24))))
            emulator.reg_write(UC_X86_REG_EAX, 0)

    cpu.hook_add(UC_HOOK_CODE, visit)
    esp = stack + 0x7000
    for widget in (native + 0x200, image + 0x8880, image + 0x6860, native + 0x300):
        for site in (0x2b90, 0x2d27, 0x312c):
            arguments = [native + 0x600, 111, 222, 1, 0, 0, 0x80123456]
            cpu.mem_write(esp, struct.pack('<7I', *arguments))
            cpu.reg_write(UC_X86_REG_ESP, esp)
            cpu.reg_write(UC_X86_REG_ECX, widget)
            cpu.reg_write(UC_X86_REG_EAX, 0x12345678)
            cpu.emu_start(image + site, image + site + 6, count=100)
            expected = arguments.copy()
            if widget != native + 0x300:
                expected[-1] = 0xff1e1e1e
            assert captures.pop() == tuple(expected)
            assert cpu.reg_read(UC_X86_REG_ESP) == esp + 28, 'MakeLayer RET 28 drift'
            assert cpu.reg_read(UC_X86_REG_ECX) == widget
            assert cpu.reg_read(UC_X86_REG_EAX) == 0xabcdef
    # Actual EXE rectangle path forwards ARGB unchanged to IWzCanvas::DrawRectangle.
    ebp = stack + 0x8000
    put(ebp + 0x20, 0xff1e1e1e)
    put(ebp + 0x1c, native + 0x2000)
    put(native + 0x2000, native + 0x1000)
    put(native + 0x108c, native + 0x3000)
    put(native + 0x4008, 476)
    put(native + 0x400c, 472)
    cpu.reg_write(UC_X86_REG_EBP, ebp)
    cpu.reg_write(UC_X86_REG_EBX, native + 0x4000)
    cpu.reg_write(UC_X86_REG_ESP, esp)
    cpu.emu_start(0x8f3478, 0x8f3493, count=100)
    assert captures.pop() == (native + 0x2000, 0, 0, 472, 476, 0xff1e1e1e)
    assert cpu.reg_read(UC_X86_REG_ESP) == esp
    for name, expected in (('终极', '%s套装 (%d/%d)'), ('终极套装', '%s (%d/%d)'),
                           ('套装', '%s (%d/%d)'), ('', '%s套装 (%d/%d)')):
        cpu.mem_write(native + 0x7000, name.encode('utf-16-le') + b'\0\0')
        put(esp + 8, native + 0x7000)
        registers = (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI)
        for index, register in enumerate(registers):
            cpu.reg_write(register, 0x11110000 + index)
        cpu.reg_write(UC_X86_REG_ESP, esp)
        cpu.emu_start(image + 0x31bd, image + 0x31c5, count=200)
        assert wide(cpu, dword(cpu, esp + 4)) == expected
        assert cpu.reg_read(UC_X86_REG_ESP) == esp
        assert [cpu.reg_read(register) for register in registers] == [0x11110000 + index for index in range(len(registers))]
    assert dword(cpu, image + 0x2f77) == 0xffa8ff53
    assert dword(cpu, image + 0x2fb6) == 0xffcbcfd7
    assert wide(cpu, dword(cpu, image + 0x3474)) == '%d件套效果'
    print('panel style ARGB/native rectangle/suffix/stack OK', hex(image))
