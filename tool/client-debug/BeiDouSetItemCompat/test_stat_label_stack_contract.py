#!/usr/bin/env python3
"""Execute the shipped lookup with real x86 stdcall stack cleanup (Unicorn)."""
import os
import struct
import sys

from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_EDX,
    UC_X86_REG_ESI, UC_X86_REG_ESP,
)

from fix_dll_reloc_hygiene import read_pe, parse_relocs, rva_to_off

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '../../../clien/BeiDouSetItemCompat.dll')
LABELS = {
    'PAD': '攻击力', 'MAD': '魔法攻击力', 'HP': '最大HP', 'MP': '最大MP',
    'FinalDamage': '最终伤害', 'BossDamage': 'Boss伤害', 'ExpRate': '经验获得',
    'DropRate': '掉落率', 'MesoRate': '金币获得',
    'PDD': '物理防御力', 'MDD': '魔法防御力', 'ACC': '命中率', 'EVA': '回避率',
    'STR': '力量', 'DEX': '敏捷', 'INT': '智力', 'LUK': '运气',
    'STRPct': '力量', 'DEXPct': '敏捷', 'INTPct': '智力', 'LUKPct': '运气',
    'PADPct': '攻击力', 'MADPct': '魔法攻击力', 'PDDPct': '物理防御力',
    'MDDPct': '魔法防御力', 'ACCPct': '命中率', 'EVAPct': '回避率',
    'HPPct': '最大HP', 'MPPct': '最大MP', 'SPD': '移动速度', 'JMP': '跳跃力',
    'NormalDamage': '普通怪物伤害', 'Damage': '伤害',
}


def text(cpu, address, width=1):
    result = bytearray()
    for index in range(256):
        part = bytes(cpu.mem_read(address + index * width, width))
        if part == b'\0' * width:
            return result.decode('ascii' if width == 1 else 'utf-16-le')
        result.extend(part)
    raise AssertionError('unterminated string')


data = open(PATH, 'rb').read()
info = read_pe(data)
_, relocations = parse_relocs(data, info)
for image in (info['image_base'], 0x78700000):
    cpu = Uc(UC_ARCH_X86, UC_MODE_32)
    cpu.mem_map(image, (info['size_of_image'] + 4095) & ~4095)
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    table = pe + 24 + struct.unpack_from('<H', data, pe + 20)[0]
    for index in range(struct.unpack_from('<H', data, pe + 6)[0]):
        size, rva, raw_size, raw = struct.unpack_from('<IIII', data, table + index * 40 + 8)
        cpu.mem_write(image + rva, data[raw:raw + raw_size])
    delta = image - info['image_base']
    for entry in relocations:
        rva = entry['rva']
        value = struct.unpack_from('<I', data, rva_to_off(info, rva))[0]
        cpu.mem_write(image + rva, struct.pack('<I', (value + delta) & 0xffffffff))
    stack, key_buffer, shim = 0x02000000, 0x03000000, 0x04000000
    cpu.mem_map(stack, 0x10000)
    cpu.mem_map(key_buffer, 0x1000)
    cpu.mem_map(shim, 0x1000)
    # lstrcmpA is stdcall: RET 8 is executed by the emulator, not inferred.
    cpu.mem_write(shim, b'\xc2\x08\x00')
    cpu.mem_write(image + 0x3100f4, struct.pack('<I', shim))
    cpu.mem_write(image + 0x310118, struct.pack('<I', shim + 16))
    ebp, esp = stack + 0x8000, stack + 0x8000 - 0x420
    captures = []

    def called(emulator, address, size, user_data):
        current = emulator.reg_read(UC_X86_REG_ESP)
        if address == shim:
            first, second = struct.unpack('<II', emulator.mem_read(current + 4, 8))
            emulator.reg_write(UC_X86_REG_EAX, 0 if text(emulator, first) == text(emulator, second) else 1)
            emulator.reg_write(UC_X86_REG_EDX, 0xdeadbeef)
        elif address == shim + 16:
            captures.append(struct.unpack('<6I', emulator.mem_read(current, 24)))
            emulator.emu_stop()

    cpu.hook_add(UC_HOOK_CODE, called)
    for key in list(LABELS) + ['', 'PDDX', 'pdd', 'HPpct', 'AllStatPct']:
        for value in (5, 50000, 1000000):
            cpu.mem_write(stack, b'\xa5' * 0x10000)
            cpu.mem_write(key_buffer, key.encode('ascii') + b'\0')
            suffix = '%' if any(token in key for token in ('Pct', 'Damage', 'Rate')) else ''
            suffix_va = image + (0x5436 if suffix else 0x5414)
            cpu.mem_write(ebp - 0x3d8, struct.pack('<I', suffix_va))
            cpu.mem_write(ebp - 0x3dc, struct.pack('<I', value))
            before = bytes(cpu.mem_read(ebp - 0x3e0, 0x3e0))
            for register, initial in ((UC_X86_REG_EBP, ebp), (UC_X86_REG_ESP, esp),
                                      (UC_X86_REG_EBX, key_buffer), (UC_X86_REG_ESI, shim)):
                cpu.reg_write(register, initial)
            cpu.emu_start(image + 0x3591, image + 0x36aa, count=2000)
            assert len(captures) == 1, (key, captures)
            ret, dest, fmt, label, actual_value, actual_suffix = captures.pop()
            assert cpu.reg_read(UC_X86_REG_ESP) == esp - 4, ('stdcall stack drift', key)
            assert ret == image + 0x36aa and dest == ebp - 0x1f8
            assert text(cpu, fmt, 2) == '%s +%d%s'
            assert text(cpu, label, 2) == LABELS.get(key, '属性'), key
            assert actual_value == value and actual_suffix == suffix_va, ('corrupt locals', key)
            assert text(cpu, actual_suffix, 2) == suffix
            assert bytes(cpu.mem_read(ebp - 0x3e0, 0x3e0)) == before, ('frame overwritten', key)
    print('x86 stdcall stack/value/suffix contract OK at', hex(image))
print('stat label stack contract OK', PATH)
