# Thunder Breaker Runtime Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the retained Thunder Breaker V/VI attacks cast reliably, match the TMS Lightning Spear timeline and visuals, enforce the requested cooldown/deletion policy, and make both Origin videos cover the full screen.

**Architecture:** Keep the existing generated WZ, Java replay scheduler, common D3D8 video renderer, and compatibility DLL boundaries. Add source-alpha-aware MCV cover scaling, complete Lightning Spear stage scheduling, and resource-level regression checks; reuse the native Shark Wave ranged branch for Shark Torpedo.

**Tech Stack:** Python 3/Pillow/FFmpeg, Java 21/Maven, C++/MinGW, WZ/MCV resources.

---

## File map

- `tool/client-video/export_thunder_breaker_mcvs.py`: decode source MCV Alpha, crop transparent bounds, and emit full-canvas MCV files.
- `tool/scripts/patch-skill/test_thunder_breaker_v_vi_contract.py`: regression checks for MCV coverage, cooldown/deletion, native Shark Wave routing, and full Lightning Spear visuals/timing.
- `tool/scripts/patch-skill/patch_thunder_breaker_v_vi.py`: generate and validate exact TMS visual nodes and all three giant-lightning triggers.
- `gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java`: replay all Lightning Spear stage effects, hits, and three giant lightning attacks.
- `tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp`: retain queued Origin playback and native Shark Wave ranged routing.
- Generated client/server WZ, MCV, DLL, docs, and download patch copy: deployable outputs.

### Task 1: Add failing regression coverage

**Files:**
- Modify: `tool/scripts/patch-skill/test_thunder_breaker_v_vi_contract.py`

- [ ] **Step 1: Test decoded full-screen Alpha coverage**

Add a test that invokes an exporter validation helper for `wave-riding-thunder.mcv` and `swift-annihilation.mcv` and expects `(0, 0, 1280, 720)`.

- [ ] **Step 2: Test the complete giant-lightning timeline**

Parse `LIGHTNING_SPEAR_GIANT_THUNDER_TIMES_MS` through `patch.java_int_array` and expect `[2820, 3150, 3480]`, derived from `w2=330` and `s2=3`.

- [ ] **Step 3: Test hidden-stage visuals and empty-target fallback**

Assert that every hidden stage plays `showThunderBreakerSpecialEffect(chr, replaySkillId)` before target selection can return, while non-empty attack packets use `replaySkillId` for exact per-monster `hit` rendering.

- [ ] **Step 4: Test the Shark Torpedo knuckle contract**

Assert that `15121001` carries legacy `weapon=48`, matching native Shark Wave,
while `weapon2=39` remains absent.

- [ ] **Step 5: Run RED**

Run: `rtk python3 -m unittest tool/scripts/patch-skill/test_thunder_breaker_v_vi_contract.py -v`

Expected: FAIL because Wave Riding Thunder does not cover the full Alpha canvas and giant lightning is scheduled once.

### Task 2: Fix full-screen MCV export

**Files:**
- Modify: `tool/client-video/export_thunder_breaker_mcvs.py`
- Modify: `clien/Data/Video/wave-riding-thunder.mcv`
- Modify: `clien/Data/Video/swift-annihilation.mcv`

- [ ] **Step 1: Generalize raw decoding to source dimensions**

Make `RawDecoder` read `width * height * 4` and return source-sized RGBA frames instead of assuming 1280×720.

- [ ] **Step 2: Compute a shared Alpha-union crop**

Decode all tracks without scaling, union every visible Alpha bound, require equal source dimensions, and fail if the union is empty.

- [ ] **Step 3: Cover-scale with the shared crop**

Apply one crop to all synchronized tracks, then use `force_original_aspect_ratio=increase` plus centered 1280×720 crop before compositing.

- [ ] **Step 4: Add reusable output validation**

Decode an output MCV and raise if its Alpha union is not `(0, 0, 1280, 720)`.

- [ ] **Step 5: Regenerate both MCVs and run GREEN for the coverage test**

Run: `rtk python3 tool/client-video/export_thunder_breaker_mcvs.py --effect wave-riding-thunder`

Run: `rtk python3 tool/client-video/export_thunder_breaker_mcvs.py --effect swift-annihilation`

Expected: both files keep their source timelines and pass full-canvas Alpha validation.

### Task 3: Complete Lightning Spear visuals and timing

**Files:**
- Modify: `gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java`
- Modify: `tool/scripts/patch-skill/patch_thunder_breaker_v_vi.py`
- Regenerate: `clien/Data/Skill/1512.img`
- Regenerate: `gms-server/wz/Skill.wz/1512.img.xml`

- [ ] **Step 1: Schedule three giant lightning attacks**

Change the Java constant to `{2820, 3150, 3480}` and derive the same list in Python validation from `finish + w2 * (1..s2)`.

- [ ] **Step 2: Preserve each hidden-stage caster animation**

Always send the hidden skill `special` before target selection can return. For a
non-empty target set, additionally send the hidden skill attack packet so the
native target-OID path plays its exact `hit`; if no target exists, return without
damage after the stage animation.

- [ ] **Step 3: Preserve exact TMS visual contracts**

Keep six distinct action/effect tracks, four ordinary thunder triggers, finish, three giant thunder triggers, eight-frame per-monster hits, and `hitAfter=390/270` for thunder/giant thunder.

- [ ] **Step 4: Regenerate and validate WZ resources**

Run: `rtk python3 tool/scripts/patch-skill/patch_thunder_breaker_v_vi.py`

Expected: 19 skills, 702 canvases, no `15121012..15121014`, exact visual/timing contracts, and requested cooldowns.

### Task 4: Verify Shark Torpedo and client dispatch

**Files:**
- Verify/modify if required: `tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp`
- Regenerate: `clien/DawnWarriorSkillCompat.dll`
- Verify: `gms-server/src/main/java/org/gms/net/server/channel/handlers/RangedAttackHandler.java`

- [ ] **Step 1: Verify the EXE branch contract**

Disassemble `0x009696A2..0x00969A54`; confirm custom `15121001` returns to the equality comparison at `0x00969730` and reaches the native Shark Wave branch at `0x00969A28`.

- [ ] **Step 2: Verify skill resources**

Confirm the client/server nodes contain `action=wave`, `effect`, `ball`, `hit`,
legacy knuckle `weapon=48`, no `weapon2` pistol classifier, and level-30 cooldown 0.

- [ ] **Step 3: Build the compatibility DLL**

Run: `rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh`

Expected: 32-bit DLL contains compatibility version 34, queued video trigger, and Shark Torpedo native gate.

### Task 5: Verify, document, and copy the patch

**Files:**
- Modify: `docs/patches/thunder-breaker-v-vi-migration.md`
- Copy in-scope files to: `/Users/lizixian/Downloads/技改/BeiDou-Server`

- [ ] **Step 1: Run targeted checks**

Run the unittest, `py_compile`, generator `--validate-only`, three `mcv_probe` checks, Java compile, DLL build, and `git diff --check`.

- [ ] **Step 2: Review the in-scope diff**

Confirm that every changed line maps to the five reported Thunder Breaker issues and unrelated dirty-worktree files remain untouched.

- [ ] **Step 3: Copy deployable files with relative paths**

Copy the generator, tests, Java handlers/constants, compatibility source/DLL, generated WZ/String/Map resources, three MCVs, and documentation into `/Users/lizixian/Downloads/技改/BeiDou-Server` while preserving repository-relative paths.

- [ ] **Step 4: Verify the copy**

Compare checksums for every copied file.

Expected: no checksum differences.
