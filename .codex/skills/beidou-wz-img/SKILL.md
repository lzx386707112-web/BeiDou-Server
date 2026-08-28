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
  [references/map-npc-mob.md](references/map-npc-mob.md).
- Items, icons, Etc/String records, quest drops, or inventory-facing resources:
  [references/item-string.md](references/item-string.md).

For Skill IMG or compatibility-DLL work, follow the repository `AGENTS.md`
skill-contract and runtime-hook sections in addition to the shared workflow.

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
- Parse independently, reject truncation or warnings, prove the raw-record
  change scope, run generators twice, and require stable SHA-256 hashes.
- Default to static verification of the modified IMG/XML and source files. Do
  not create temporary packed WZ files or build JAR/DLL artifacts unless the
  user explicitly requests that output in the current task.
- Never copy unverified artifacts to Downloads or another delivery location.

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

## Stopping conditions

Stop before writing when the baseline, region/key, target record, source chain,
or compatible schema cannot be established from evidence. Stop before delivery
when any protected record changed, a generator is not idempotent, an IMG has a
warning, or a Canvas cannot be decoded.
