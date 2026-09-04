#pragma once

// ============================================================
// patch_common.h -- shared low-level helpers for the split-out
// patch_*.cpp files. Thin typed wrappers over PatchMemory()
// (declared in hook.h). These were previously file-static
// helpers inside patches.cpp.
// ============================================================

#include "hook.h"

inline void PatchDouble(uintptr_t addr, double value) {
    PatchMemory(reinterpret_cast<void*>(addr), &value, sizeof(double));
}

inline void PatchInt(uintptr_t addr, int value) {
    PatchMemory(reinterpret_cast<void*>(addr), &value, sizeof(int));
}

inline void PatchBytes(uintptr_t addr, const unsigned char* bytes, size_t len) {
    PatchMemory(reinterpret_cast<void*>(addr), const_cast<unsigned char*>(bytes), len);
}
