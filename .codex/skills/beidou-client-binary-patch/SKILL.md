---
name: beidou-client-binary-patch
description: Safely patch the BeiDou-Server 32-bit client binaries (BeiDou.exe and compatibility DLLs under clien/) with byte-level, evidence-backed changes — suppressing a crash, skipping a call/exception, guarding a stale pointer. Use for any task that edits a shipped binary rather than WZ/IMG data, and for diagnosing first-chance exceptions or access violations reported by the diagnostic DLLs.
agent_created: true
---

# BeiDou client binary patch workflow

Use this skill only in the `BeiDou-Server` repository, for `clien/*.exe` and
`clien/*.dll` edits. For WZ/IMG resources use `beidou-wz-img` instead.

The repository `AGENTS.md` rules still apply: smallest evidence-backed change,
preserve the worktree, never full-tree rewrite a binary, replays and gates
before delivery.

## Worked examples to copy from

- `tool/client-debug/wz-file-logger-fix/` — code-cave stub + guard, DLL with
  `DYNAMIC_BASE` (stub must be position independent).
- `tool/client-debug/beidou-skip-media-com-error/` — 1-byte
  `jge` → `jmp` to skip a `_com_error` throw, fixed-ImageBase EXE.

Both follow the same layout: `README.md`, `patch_<name>.py`,
`test_<name>_contract.py`, `backup/<file>.orig`. Copy that layout for new work.

## Step 1 — get the evidence before touching a byte

1. `git status --short` first. `clien/BeiDou.exe` is git-tracked, so a pristine
   baseline is recoverable with
   `git cat-file blob HEAD:clien/BeiDou.exe > /tmp/base.exe`.
   **Never** `rtk git show > binary-file`; RTK filtering corrupts binary stdout.
2. Read the newest `clien/diagnostics/session-*.log`. Match the fault to a
   module+RVA (`WzFileLogger.dll+0x24f4`) and to a first-chance record
   (`first_chance_cpp code=0xe06d7363` = MSVC `_com_error`;
   `exception_info="i0=0x19930520;..."` is the C++ EH magic).
3. Parse the matching `.dmp` and cross-check the throw site by its **arguments**,
   not by the nominal frame. See "Frame semantics" below.

## Step 2 — pin the exact patch site

Disassemble with `i686-w64-mingw32-objdump -d -M intel --start-address=…
--stop-address=…`. Two idioms recur in this client:

- **Exception suppression**: `test %eax,%eax` / `jge <normal>` /
  `push <riid>` / `push %obj` / `push %eax` / `call _com_raise_error`.
  Converting `jge` (`0x7d`) to `jmp` (`0xeb`) is a **1-byte** fix that sends the
  failure down the function's normal continuation. Prefer it over NOP-ing the
  whole block: the dead bytes stay intact and the diff stays minimal.
- **Stale-pointer guard**: a cached module RVA dereferenced with only a NULL
  check; add a `VirtualQuery` + `AllocationBase` validation stub in `.text`
  tail padding.

Before patching, prove the target block is dead: no relative branch anywhere in
the section may land inside it. Both relative encodings must be checked —
`e8/e9 rel32`, `0f 8x rel32`, `7x rel8`.

## Step 3 — frame semantics traps (cost the most time)

- `mov eax,<imm>; call <helper>` at function entry is `__EH_prolog3_catch`
  (e.g. `BeiDou.exe` `0xa60b98`). It **does** establish `ebp`, even though the
  source has no `push ebp; mov ebp,esp`. So `[ebp+8]`, `[ebp-0xc]`,
  `mov fs:0,ecx` in the epilogue are ordinary frame locals, not garbage.
- `[ebp+8]` is not always arg1's *value*. Check the epilogue: a function that
  ends `mov eax,[ebp+8]` **returns arg1**, and `_com_raise_error`'s frame is
  3 args (`hr`, `pUnk`, `riid`). Attribute a dump frame by matching the push
  order, e.g. `push 0xbd8318 / push ebx / push eax` → `[ebp+8]=hr`,
  `[ebp+0xc]=pUnk`, `[ebp+0x10]=riid`.
- Argument slots of a frameless-looking helper may be **compiler stack-slot
  reuse**: at a bare `call X` with no preceding `push`, `X`'s `[ebp+8]` /
  `[ebp+0xc]` are leftovers from earlier pushes. Reconstruct the whole sequence
  and subtract each callee's `ret n` to know which value sits where. This is
  how you decide whether a recovered pointer will be NULL — and therefore
  whether skipping an exception leads to a graceful branch or a NULL deref.
- Before declaring a skip safe, find the caller's explicit failure branch
  (`cmp eax,ebx(0)` / `je <benign path>`). If the caller already has a
  "result is empty → return E_NOINTERFACE, no throw" arm, the skip is by design.

## Step 4 — PE layout gotchas

- Section header field order is `VirtualSize(+8)`, `VirtualAddress(+12, RVA —
  not the absolute VA)`, `SizeOfRawData(+16)`, `PointerToRawData(+20)`.
  Getting these off by four silently "passes" then fails.
- CheckSum field = `e_lfanew + 24 + 64`. Recompute it after any patch
  (algorithm: sum 16-bit words with the field zeroed, fold carry, add file
  length).
- Read `DllCharacteristics` (`opt + 70`). `0x0040` = `DYNAMIC_BASE`: then any
  stub must be position independent. `BeiDou.exe` is `0x0000` with ImageBase
  `0x400000`, so in-place bytes need no relocations.
- If `SizeOfRawData == VirtualSize`, the section's tail zero padding is mapped
  RX and is a safe code cave — but do **not** use `0xAEFA20`, which already
  holds the loader thunk for `DawnWarriorSkillCompat.dll`.

## Step 5 — verify, and verify the right property

`test_*_contract.py` must assert more than "the bytes changed":

- one code byte differs from `backup/*.orig` plus at most the 4-byte checksum
  field — enumerate the diff offsets and bound them;
- the patched instruction decodes to what you intended (capstone;
  **only `/opt/homebrew/bin/python3` has capstone**, the managed venv does not);
- **reachability, not presence**: dead bytes remain in the file, so a
  "`call _com_raise_error` no longer appears in the function" assertion is
  wrong. Do a DFS from the function entry over fall-through plus direct branch
  edges, and assert the throw is unreachable — then run the same analysis on the
  backup and assert it *was* reachable. That differential is the real proof.
- PE checksum self-consistent, section headers, section count and file size all
  unchanged.

Run the patch script twice and require the second run to report
`already patched` with an unchanged sha256.

## Step 6 — deliver

- Deliver only the changed binary to `~/Downloads/<中文功能名>/` plus a short
  `说明.txt` (what changed, sha256 before/after, how to roll back). Keep the
  original in `tool/client-debug/<name>/backup/`.
- Do not claim the fix works at runtime. State the runtime gate explicitly: the
  user must launch the client and check `clien/diagnostics/session-*.log` for
  the absence of the matching `first_chance_cpp` / `crash` record.
