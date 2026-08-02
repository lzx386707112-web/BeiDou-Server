# Thunder Breaker V/VI Compatibility Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the retained Thunder Breaker V/VI attacks cast reliably, preserve their TMS timelines and visuals, apply the requested cooldown policy, and remove Annihilate VI.

**Architecture:** Keep the existing generated WZ resources, Java replay scheduler, and compatibility DLL boundaries. Queue Thunder Breaker MCV playback until the next D3D8 Present, route Shark Torpedo through the complete native Shark Wave branch, and make Lightning Spear stages acquire targets from the main cast range while retaining each stage's own effect, hit, damage, and timing data.

**Tech Stack:** Python WZ generator, Java/Maven server, C++/MinGW compatibility DLL, MCV/VP9 video resources.

---

### Task 1: Add regression contracts

**Files:**
- Create: `tool/scripts/patch-skill/test_thunder_breaker_v_vi_contract.py`

- [ ] **Step 1: Write tests for the requested skill set and cooldowns**

Assert that `15121012` is absent and that only `15121017` and `15121019` have a 10-second effective cooldown.

- [ ] **Step 2: Write tests for runtime compatibility paths**

Assert that the DLL queues Thunder Breaker videos at Present, Shark Torpedo returns to the native equality comparison, and the Java scheduler uses the main Lightning Spear range plus an empty-target visual fallback.

- [ ] **Step 3: Run the test and verify RED**

Run: `rtk python3 -m unittest tool/scripts/patch-skill/test_thunder_breaker_v_vi_contract.py -v`

Expected: FAIL because the old implementation retains Annihilate VI, source cooldowns, the immediate video call, the deep Shark Torpedo jump, and hidden-stage target ranges.

### Task 2: Fix generated skill resources

**Files:**
- Modify: `tool/scripts/patch-skill/patch_thunder_breaker_v_vi.py`
- Modify: `gms-server/src/main/java/org/gms/constants/skills/ThunderBreaker.java`
- Modify: `docs/patches/thunder-breaker-v-vi-migration.md`

- [ ] **Step 1: Remove Annihilate VI from generated skills and defaults**

Delete target `15121012` and its now-unused hit/mob compatibility code while retaining the cleanup range so an existing node is removed on regeneration.

- [ ] **Step 2: Add the local cooldown policy**

Keep TMS source cooldown validation intact, but generate cooldown `10` for `15121017/15121019` and `0` for every other retained target.

- [ ] **Step 3: Add Lightning Spear empty-target special tracks**

For hidden stages `15121003..15121011`, expose the exact source `effect` animation through `special`, so a scheduled stage remains visible after its prior target dies.

- [ ] **Step 4: Regenerate and validate resources**

Run: `rtk python3 tool/scripts/patch-skill/patch_thunder_breaker_v_vi.py`

Expected: validation reports 19 retained skills, no `15121012`, matching TMS parameters apart from the explicit cooldown policy.

### Task 3: Fix server replay targeting and visuals

**Files:**
- Modify: `gms-server/src/main/java/org/gms/net/server/channel/handlers/CloseRangeDamageHandler.java`

- [ ] **Step 1: Select Lightning Spear targets with the main cast effect**

Pass the original `15121002` effect as the range effect for all hidden Lightning Spear stages while continuing to use each replay effect for attack count, mob count, damage scaling, and hit visuals.

- [ ] **Step 2: Play a stage effect when no live target remains**

When a Lightning Spear hidden replay finds no target, send its remapped `special` effect and return without damage.

- [ ] **Step 3: Compile the server**

Run: `rtk mvn -pl gms-server -am -DskipTests compile`

Expected: BUILD SUCCESS.

### Task 4: Fix client dispatch and full-screen playback

**Files:**
- Modify: `tool/client-debug/dawn-warrior-skill-compat/DawnWarriorSkillCompat.cpp`
- Modify: `tool/client-debug/dawn-warrior-skill-compat/README.md`
- Modify: `clien/DawnWarriorSkillCompat.dll`

- [ ] **Step 1: Queue Thunder Breaker MCV playback**

Store the requested video skill ID during active-skill dispatch and consume it from the next hooked D3D8 Present after the melee constructor has completed.

- [ ] **Step 2: Restore the complete native Shark Wave branch**

For `15121001`, load that ID into `eax` and return to `0x00969730`, allowing the native equality jump through `0x00969A28` before the ranged constructor.

- [ ] **Step 3: Build and inspect the DLL**

Run: `rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh`

Expected: the DLL builds and exported code contains the queued video and native Shark Torpedo route.

### Task 5: Verify and package

**Files:**
- Copy all modified patch files to `/Users/lizixian/Downloads/技改/BeiDou-Server`

- [ ] **Step 1: Run regression and resource checks**

Run the unittest, `py_compile`, generator `--validate-only`, MCV probes, Maven compile, and `git diff --check`.

- [ ] **Step 2: Review only in-scope diffs**

Confirm every changed line maps to the five requested Thunder Breaker behaviors and no unrelated dirty-worktree files were modified.

- [ ] **Step 3: Synchronize and compare the patch directory**

Copy the modified files with relative paths and run a checksum/dry-run comparison.

Expected: comparison produces no differences.
