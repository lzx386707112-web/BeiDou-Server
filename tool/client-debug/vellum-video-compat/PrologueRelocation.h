// Whole instruction prologue relocation for the d3d8!Direct3DCreate8 detour.
//
// 2026-09-28 (v4): the phone run crashed with STATUS_ILLEGAL_INSTRUCTION at trampoline+4 while
// the PC ran the very same binaries. The v3 hook overwrote a fixed five bytes at the function
// entry and copied those same five bytes into its trampoline, which assumes the target's first
// instruction boundary falls exactly on offset 5. That held for the Microsoft d3d8.dll the PC
// loads, but not for the Wine builtin d3d8.dll the phone loads. A prologue such as
//
//     53            push %ebx
//     55            push %ebp
//     8B EC         mov  %esp,%ebp
//     C7 45 F8 00 00 00 00   movl $0,-8(%ebp)     <- starts at offset 4
//
// loses the ModRM byte of that last instruction to the 0xE9 opcode, so the trampoline decodes
// `C7 E9`, whose /5 opcode extension is undefined (#UD). The fix is to relocate whole
// instructions: walk the prologue, copy N bytes (N >= 5), patch all N bytes at the entry and
// resume at target + N.
//
// A rejected answer is always safe: the caller falls back to the probe interface capture, which
// patches only the IDirect3D8 vtable and never executes generated code.
//
// This header is deliberately free of Windows dependencies so the decoder can be unit tested by
// compiling it with a host compiler.

#ifndef BEIDOU_PROLOGUE_RELOCATION_H_
#define BEIDOU_PROLOGUE_RELOCATION_H_

#include <stddef.h>

namespace beidou {
namespace prologue {

// Length of the memory operand addressed by the ModRM byte at code[1], or 0 when the instruction
// cannot be relocated verbatim. A displacement that does not come from a register (disp32 with a
// missing base, or a SIB without a base) encodes the instruction's own absolute position, so it
// would stop being valid once the instruction is moved elsewhere.
inline size_t ModRmLength(const unsigned char* code, size_t available) {
    if (code == nullptr || available < 2) return 0;
    const unsigned char modrm = code[1];
    const unsigned char mod = static_cast<unsigned char>(modrm >> 6);
    const unsigned char rm = static_cast<unsigned char>(modrm & 0x07);
    if (mod == 3) return 2;  // register operand, no memory reference, no displacement

    size_t length = 2;
    if (rm == 4) {  // SIB byte follows
        if (available < 3) return 0;
        const unsigned char base = static_cast<unsigned char>(code[2] & 0x07);
        if (mod == 0 && base == 5) return 0;  // disp32 only
        length = 3;
    } else if (mod == 0 && rm == 5) {
        return 0;  // disp32 only
    }
    if (mod == 1) {
        length += 1;
    } else if (mod == 2) {
        length += 4;
    }
    return length <= available ? length : 0;
}

inline size_t ModRmImmediateLength(const unsigned char* code, size_t available, size_t immediate) {
    const size_t base = ModRmLength(code, available);
    if (base == 0) return 0;
    return base + immediate <= available ? base + immediate : 0;
}

// Length of the single instruction at `code`, or 0 when it must not be relocated verbatim.
inline size_t InstructionLength(const unsigned char* code, size_t available) {
    if (code == nullptr || available == 0) return 0;
    const unsigned char opcode = code[0];

    switch (opcode) {
        // Prefixes and the 0x0F escape: a prefix only changes the following opcode, and 0x0F
        // starts a two byte opcode this decoder does not model.
        case 0x0F: case 0x26: case 0x2E: case 0x36: case 0x3E:
        case 0x64: case 0x65: case 0x66: case 0x67: case 0xF0: case 0xF2: case 0xF3:
        // Legacy segment / BCD opcodes no modern compiler emits in a prologue.
        case 0x06: case 0x07: case 0x0E: case 0x16: case 0x17: case 0x1E: case 0x1F:
        case 0x27: case 0x2F: case 0x37: case 0x3F:
        // BOUND / ARPL.
        case 0x62: case 0x63:
        // Far transfers, returns, ENTER/LEAVE, software interrupts and port IO.
        case 0x9A: case 0xC2: case 0xC3: case 0xC8: case 0xC9: case 0xCA: case 0xCB:
        case 0xCC: case 0xCD: case 0xCE: case 0xCF:
        case 0xE0: case 0xE1: case 0xE2: case 0xE3: case 0xE4: case 0xE5: case 0xE6: case 0xE7:
        // Relative branches: their displacement is measured from the instruction's own position.
        case 0xE8: case 0xE9: case 0xEB:
        case 0xEC: case 0xED: case 0xEE: case 0xEF:
            return 0;
        default:
            break;
    }
    if (opcode >= 0x70 && opcode <= 0x7F) return 0;  // conditional short branches
    // moffs32 forms carry the absolute address of the operand.
    if (opcode == 0xA0 || opcode == 0xA1 || opcode == 0xA2 || opcode == 0xA3) return 0;

    if (opcode < 0x40) {
        // 0x00..0x3F: four ModRM forms per ALU family, then the accumulator immediate forms.
        const unsigned char form = static_cast<unsigned char>(opcode & 0x07);
        if (form <= 3) return ModRmLength(code, available);
        if (form == 4) return available >= 2 ? 2 : 0;  // op al, imm8
        if (form == 5) return available >= 5 ? 5 : 0;  // op eax, imm32
        return 0;                                      // segment / BCD forms
    }
    if (opcode <= 0x5F) return 1;                      // inc/dec r32, push/pop r32
    if (opcode == 0x68) return available >= 5 ? 5 : 0;  // push imm32
    if (opcode == 0x69) return ModRmImmediateLength(code, available, 4);
    if (opcode == 0x6A) return available >= 2 ? 2 : 0;  // push imm8
    if (opcode == 0x6B) return ModRmImmediateLength(code, available, 1);
    if (opcode >= 0x80 && opcode <= 0x83) {
        return ModRmImmediateLength(code, available, opcode == 0x81 ? 4 : 1);
    }
    if (opcode >= 0x84 && opcode <= 0x8F) return ModRmLength(code, available);
    if (opcode >= 0x90 && opcode <= 0x99) return 1;    // xchg / cwde / cdq / nop
    if (opcode == 0x9B || opcode == 0x9C || opcode == 0x9D ||
        opcode == 0x9E || opcode == 0x9F) {
        return 1;                                      // wait / pushfd / popfd / sahf / lahf
    }
    if (opcode >= 0xA4 && opcode <= 0xA7) return 1;     // movs / cmps
    if (opcode == 0xA8) return available >= 2 ? 2 : 0;
    if (opcode == 0xA9) return available >= 5 ? 5 : 0;
    if (opcode >= 0xAA && opcode <= 0xAF) return 1;     // stos / lods / scas
    if (opcode >= 0xB0 && opcode <= 0xB7) return available >= 2 ? 2 : 0;
    if (opcode >= 0xB8 && opcode <= 0xBF) return available >= 5 ? 5 : 0;
    if (opcode == 0xC0 || opcode == 0xC1) return ModRmImmediateLength(code, available, 1);
    if (opcode == 0xC6) return ModRmImmediateLength(code, available, 1);
    if (opcode == 0xC7) return ModRmImmediateLength(code, available, 4);
    if (opcode >= 0xD0 && opcode <= 0xD3) return ModRmLength(code, available);
    if (opcode >= 0xD8 && opcode <= 0xDF) return ModRmLength(code, available);  // x87
    if (opcode == 0xF6 || opcode == 0xF7) {
        if (available < 2) return 0;
        const unsigned char extension = static_cast<unsigned char>((code[1] >> 3) & 0x07);
        if (extension > 1) return ModRmLength(code, available);
        return ModRmImmediateLength(code, available, opcode == 0xF7 ? 4 : 1);
    }
    if (opcode == 0xFE || opcode == 0xFF) return ModRmLength(code, available);
    return 0;
}

// Number of whole prologue bytes to relocate so that at least `minimum` bytes are covered, or 0
// when the window cannot be relocated safely. One rejected byte rejects the whole window.
inline size_t RelocationLength(
    const unsigned char* code, size_t available, size_t minimum, size_t maximum) {
    if (code == nullptr || minimum == 0 || maximum < minimum) return 0;
    size_t total = 0;
    while (total < minimum) {
        if (total >= maximum) return 0;
        const size_t length = InstructionLength(code + total, available - total);
        if (length == 0) return 0;
        total += length;
    }
    return total > maximum ? 0 : total;
}

}  // namespace prologue
}  // namespace beidou

#endif  // BEIDOU_PROLOGUE_RELOCATION_H_
