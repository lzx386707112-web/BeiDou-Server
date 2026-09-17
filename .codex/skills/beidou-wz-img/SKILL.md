---
name: beidou-wz-img
description: Safely diagnose, add, edit, migrate, statically verify, or deliver BeiDou-Server client WZ/IMG resources and matching server XML, including quests, maps, NPCs, mobs, items, strings, effects, and Workbench resource operations. Use for any task in this repository that reads or changes WZ/IMG data or investigates old-client “incorrect game data” failures.
---

# BeiDou WZ/IMG compatibility workflow

Use this skill only in the `BeiDou-Server` repository. Treat client IMG files as
binary compatibility artifacts, not ordinary serialized trees.

## Required reading

For every task that may change an IMG, WZ, or matching XML, read
[references/wzskill.md](references/wzskill.md) and
[references/verification.md](references/verification.md) completely before
editing.

Then read only the references matching the requested surface:

- Quest IMG, quest XML, quest scripts, or Workbench task-platform changes:
  [references/quest.md](references/quest.md).
- Maps, life nodes, NPCs, mobs, bosses, or their String records:
  [references/map-npc-mob.md](references/map-npc-mob.md). When migrating
  maps or mobs, that file’s gap / `connect` rope / ballistic sections are
  required, not optional.
- Damien (`8880110`/`8880111`) combat, `DamienBossCompat`, skill2 orbs:
  `.codex/skills/beidou-damien-boss/SKILL.md` (or `.cursor/skills/beidou-damien-boss/SKILL.md`).
- Items, icons, Etc/String records, quest drops, or inventory-facing resources:
  [references/item-string.md](references/item-string.md).

For Skill IMG or compatibility-DLL work, follow the repository `AGENTS.md`
skill-contract and runtime-hook sections in addition to the shared workflow.

For a server-scheduled multi-hit replay that needs caster-local damage numbers,
read [references/indexed-replay-damage-numbers.md](references/indexed-replay-damage-numbers.md)
before editing. It defines the evidence gate, reserved packet markers, native
`120ms * hitIndex` cadence, display-vs-damage separation, and the reusable
`NONE`/`TOTAL`/`INDEXED` integration pattern.

## Non-negotiable invariants

- Start with `rtk git status --short`; preserve every pre-existing change.
- Establish a last-known-working raw baseline and an explicit approved record
  set before writing.
- Never full-serialize an existing client IMG merely to edit selected nodes.
  `encode_image_body()`, `save_as()`, parse-and-reserialize, and delete/reappend
  are forbidden unless the user explicitly authorizes a proven whole-file
  migration.
- Prefer same-length payload edits, then raw record replacement, then raw
  record insertion. Preserve untouched record bytes and sibling order.
- Project modern TMS data onto an old-client structure proven by a working
  analogue. Do not copy a modern schema wholesale.
- Keep client, server XML, String data, scripts, drops, and runtime code in one
  audited contract. Do not assume editing an `.img.xml` changes the client IMG.
- `gms-server/wz-zh-CN` may contain only `Etc.wz`, `Quest.wz`, and `String.wz`.
  Never add Map, Mob, Npc, Item, Skill, Character, Reactor, Sound, or UI under
  that tree. `WZFiles.getFile()` uses the whole language WZ if the folder exists,
  so a partial `wz-zh-CN/Map.wz` hides `wz/Map.wz` and logs
  `MapFactory: missing map data`. Put map/mob/NPC XML in `gms-server/wz`. Put
  Chinese names in `wz-zh-CN/String.wz`.
- Parse independently, reject truncation or warnings, prove the raw-record
  change scope, run generators twice, and require stable SHA-256 hashes.
- Default to static verification of the modified IMG/XML and source files. Do
  not create a temporary packed WZ, and do not build the server JAR, unless
  the user explicitly requests that artifact.
- Compatibility DLLs are part of delivery. If the task changed DLL source,
  routing, or a runtime that depends on a rebuilt DLL, compile it with the
  checked-in build script without waiting for a separate authorization.
- Never copy unverified artifacts to Downloads or another delivery location.
- After the requested fix is verified, deliver **only this task's modified
  runtime files** to `/Users/lizixian/Downloads/<本次功能中文名>/`.
  Name the folder after this task's function, never a fixed boss name.
  See [Delivery scope](#delivery-scope).

## Work sequence

1. Classify the failure: startup compatibility, parsing, visual/runtime,
   quest/data contract, drop/source, or delivery mismatch.
2. Record the suspected cause, allowed files and record paths, baseline,
   success criteria, and required checks.
3. Inspect the TMS/MS source chain and a compatible legacy analogue.
4. Implement the smallest incremental generator or record patch. If only a
   full writer exists, stop and add an incremental path first.
5. Update the matching server-side contract without rewriting unrelated XML.
6. Run the relevant reference-specific audits and the shared verification
   gates.
7. Inspect `rtk git diff --check`, final status, raw-record scope, and hashes.
8. State what offline checks proved and what still needs a real old-client
   launch or in-game test.

## Compatibility DLL build and delivery

A completed client fix is not done after source and static checks if a
compatibility DLL participates in the runtime contract. Do not wait for the
user to authorize the DLL build.

After static gates pass:

1. Run the DLL's checked-in project build script (for example
   `tool/client-debug/set-item-compat/build.sh`). Do not substitute an ad hoc
   compiler command that may omit linker or compatibility flags.
2. Verify that the output is the expected 32-bit Windows DLL and inspect its
   repository path and SHA-256 hash.
3. If this task rebuilt the DLL, copy that DLL with the other files this
   task modified to `/Users/lizixian/Downloads/<本次功能中文名>/`, preserving in-client
   paths (DLL at the client root, for example `BeiDouSetItemCompat.dll`).
4. Compare source and delivered SHA-256 hashes for every copied file and
   require an exact match.
5. Report the build result, the delivery list for **this task only**, matching
   hashes, and remaining real-client checks.

Do not omit the DLL because only IMG or Java changed if the DLL routing was
also edited in the same task.

## Delivery scope

Each delivery is a delta for the current user request, not a recap of the
feature or of earlier turns in the same chat.

- Recreate the `/Users/lizixian/Downloads/<本次功能中文名>/` directory (or
  clear its contents) so it contains only this task's payload. Name the
  folder in Chinese from the function that changed. Do not reuse a fixed
  name such as `路西德`.
- Copy only runtime files this task created or modified after static gates
  pass: client IMGs/strings/MCV/Effect/DLLs, matching server XML, and scripts
  that actually changed. Preserve in-client relative paths (`Data/...` under
  `clien/Data/`, DLLs at the `clien/` root, server files under `gms-server/`).
- Do not re-copy files that this task did not change, even if they belong to
  the same map, skill, NPC, course, or a prior delivery in this conversation.
- Do not copy unchanged siblings from the same directory.
- Do not include unrelated worktree changes, baselines, backups, generated
  packages, probe files, or verification WZ packages.
- Compare SHA-256 hashes between source and destination for every copied file.
- Report the exact file list. If the user later asks to sync again without new
  edits, say there is nothing new to deliver.

## Stopping conditions

Stop before writing when the baseline, region/key, target record, source chain,
or compatible schema cannot be established from evidence. Stop before delivery
when any protected record changed, a generator is not idempotent, an IMG has a
warning, or a Canvas cannot be decoded.
