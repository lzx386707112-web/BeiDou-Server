"""Layout extension used only by the unified baseline-to-DLL generator."""
import os
import struct
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CAVE_RVA, CAVE_RAW = 0x312900, 0x5300
STYLE_STRINGS_RVA, STYLE_STRINGS_RAW = 0x312f00, 0x5900
STYLE_TEXT = ((0, '%s套装 (%d/%d)'), (0x30, '%d件套效果'))
RETAINED_RELOCS = {0x3474, 0x3498}
DRAW_SITES = (0x3204, 0x33b8, 0x33de, 0x3426, 0x34b6, 0x36db)
LAYOUT_WINDOWS = ((0x2b54, 0x2b5a), (0x23df, 0x23e6), (0x2451, 0x2457),
                  (0x3012, 0x3018), (0x306d, 0x3072), (0x307a, 0x3080),
                  (0x30d8, 0x30e0), (0x30e0, 0x30ea), (0x30ea, 0x30ed),
                  (0x322b, 0x3231), (0x3237, 0x323d)) + tuple(
                      (rva, rva + 5) for rva in DRAW_SITES + (0x3063, 0x3749)) + (
    (0x2b90, 0x2b96), (0x2d27, 0x2d2d), (0x312c, 0x3132),
    (0x2f76, 0x2f7b), (0x2fb5, 0x2fba), (0x31bd, 0x31c5),
    (0x3470, 0x3478), (0x3496, 0x349c), (0x349c, 0x34a3), (0x36c1, 0x36c8))


def build_helpers():
    with tempfile.TemporaryDirectory(prefix='beidou-set-layout-') as directory:
        objects = []
        for source in ('set_panel_layout.S', 'set_panel_layout.c'):
            output = os.path.join(directory, source + '.o')
            subprocess.run(['i686-w64-mingw32-gcc', '-c', '-Os', '-fno-ident',
                            '-fno-asynchronous-unwind-tables', '-fno-unwind-tables',
                            '-fno-stack-protector', '-fno-jump-tables', '-mno-sse',
                            os.path.join(HERE, source), '-o', output], check=True)
            objects.append(output)
        linked, raw = os.path.join(directory, 'helpers.exe'), os.path.join(directory, 'helpers.bin')
        subprocess.run(['i686-w64-mingw32-ld', '-Ttext', hex(CAVE_RVA), '--image-base', '0',
                        '--section-alignment', '16', '--file-alignment', '16',
                        '-e', 'collect_panel', *objects, '-o', linked], check=True)
        subprocess.run(['i686-w64-mingw32-objcopy', '-O', 'binary', '-j', '.text', linked, raw], check=True)
        symbols = {}
        for line in subprocess.check_output(['i686-w64-mingw32-nm', linked], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[1] in ('T', 't'):
                symbols[parts[2]] = int(parts[0], 16)
        code = open(raw, 'rb').read()
        assert len(code) <= STYLE_STRINGS_RAW - CAVE_RAW, len(code)
        return code, symbols


def apply_layout(data, ftext):
    code, symbols = build_helpers()
    assert data[CAVE_RAW:CAVE_RAW + len(code)] == b'\0' * len(code)
    windows = []

    def patch(rva, old, new):
        old = bytes.fromhex(old)
        offset = ftext(rva)
        assert data[offset:offset + len(old)] == old, (hex(rva), data[offset:offset + len(old)].hex())
        assert len(new) <= len(old)
        data[offset:offset + len(old)] = new.ljust(len(old), b'\x90')
        windows.append((rva, rva + len(old)))

    def call(rva, old, name, jump=False):
        patch(rva, old, (b'\xe9' if jump else b'\xe8') + struct.pack('<i', symbols[name] - rva - 5))

    call(0x2b54, '81ecfc030000', 'allocate_frame')
    call(0x23df, '83bd9cfeffff09', 'save_slot')
    # Both name copies are complete; the last two padding bytes hold the slot ID.
    call(0x2451, '83ec0cff466c', 'store_slot')
    call(0x3012, '8b854cfcffff', 'save_widget')
    call(0x306d, 'e80debffff', 'collect_panel')
    patch(0x307a, '8b8728cae065', bytes.fromhex('8b85f0efffff'))
    call(0x30d8, 'c1e004b98088c865', 'size_panel')
    patch(0x30e0, 'c7058c88c865ec000000', b'')
    patch(0x30ea, '83c01c', b'')
    patch(0x322b, '3b8728cae065', bytes.fromhex('3b85f0efffff'))
    call(0x3237, '8b9d44fcffff', 'select_slot', jump=True)
    for rva in DRAW_SITES:
        old = 'e8' + struct.pack('<i', 0x174d - rva - 5).hex()
        call(rva, old, 'draw_column')
    for rva in (0x3063, 0x3749):
        old = 'e8' + struct.pack('<i', 0x2a75 - rva - 5).hex()
        call(rva, old, 'position_panel')
    for rva in (0x2b90, 0x2d27, 0x312c):
        call(rva, 'ff1594a8c865', 'make_dark_layer')
    patch(0x2f76, 'ba37e1ffff', b'\xba' + struct.pack('<I', 0xffa8ff53))
    patch(0x2fb5, 'bad2d2d2ff', b'\xba' + struct.pack('<I', 0xffcbcfd7))
    call(0x31bd, 'c74424047655c865', 'format_title')
    patch(0x3470, 'c7442404a055c865', b'\xc7\x44\x24\x04' + struct.pack('<I', 0x65c80000 + STYLE_STRINGS_RVA + 0x30))
    patch(0x3496, '8b156888c865', bytes.fromhex('8b156c88c865'))
    patch(0x349c, '0f4c156088c865', b'')
    patch(0x36c1, '0f4c156088c865', b'')
    for offset, text in STYLE_TEXT:
        encoded = text.encode('utf-16-le') + b'\0\0'
        start = STYLE_STRINGS_RAW + offset
        assert data[start:start + len(encoded)] == b'\0' * len(encoded)
        data[start:start + len(encoded)] = encoded
    data[CAVE_RAW:CAVE_RAW + len(code)] = code
    assert tuple(windows) == LAYOUT_WINDOWS
    return windows, len(code), symbols
