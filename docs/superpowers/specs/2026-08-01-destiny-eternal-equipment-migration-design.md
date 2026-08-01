# Destiny and Eternal Equipment Migration Design

## Goal

Migrate the final-state TMS Destiny weapons and matching Eternal armor for
Adventurers, Cygnus Knights, and Aran into BeiDou. The migration is limited to
equipment items and wearable visuals. It does not add Destiny progression,
quests, particles, set effects, or modern upgrade systems.

## Scope

- 16 final-state Destiny weapons in the legacy weapon families supported by
  BeiDou.
- 30 Eternal armor pieces: five job families across cap, cape, coat, glove,
  pants, and shoes.
- Exclude all five Eternal shoulder items because BeiDou has no shoulder slot
  in its player equipment panel.
- Exclude Cannon, Ancient Bow, and all weapons for jobs outside Adventurers,
  Cygnus Knights, and Aran.

## Item Data Policy

- Change `reqLevel` from 250 to 200 for all 46 items.
- Preserve `reqJob`, ordinary base stats, weapon attack speed, slot metadata,
  and all wearable pose data.
- Preserve the source upgrade slot counts: 9 for weapons, 12 for caps, and 8
  for the other armor pieces.
- Remove fields that block normal BeiDou scrolling, upgrading, trading,
  dropping, selling, or decomposition.
- Remove modern-only mechanism fields, including Destiny set membership,
  set-joker behavior, Boss reward metadata, and fields whose behavior BeiDou
  does not implement.
- Remove `bdR` and `imdR`: BeiDou does not apply these item-info fields to the
  equipped-item stat object, so retaining them would make the client display
  effects that the server does not grant.
- Add `limitBreak=2147483647` to weapons, matching BeiDou's weapon
  compatibility convention.

## Resource Conversion

Implement an idempotent migration script under `tool/scripts/migration`.
Read TMS IMG files with the BMS key and write BeiDou client IMG files with the
GMS key.

Every selected TMS item uses 1x1 Canvas placeholders whose `_outlink` points
to a separate `_Canvas` IMG. Resolve each link, decode the real source Canvas,
encode it into the destination item IMG, retain its child metadata, and omit
the `_outlink`. Strip the Destiny weapon particle branches because BeiDou does
not contain the referenced particle resource.

Generate matching XML files under `gms-server/wz/Character.wz` from the same
materialized item tree. Add the 46 item names to the client String/Eqp IMG and
both server String/Eqp XML files without changing unrelated entries.

## Safety

- Preflight all source items and Canvas links before writing outputs.
- Use atomic writes for the two shared binary/XML string resources.
- Update only the 46 selected item IDs; do not delete or replace other items.
- Do not edit shoulder-slot code or level-cap configuration.
- Preserve all unrelated dirty-worktree changes.

## Verification

- Confirm exactly 46 client IMG and 46 server XML item files exist.
- Parse every client IMG with the GMS key and decode every embedded Canvas.
- Assert no selected item contains `_outlink`, unresolved particle references,
  or a 1x1 placeholder standing in for a linked source Canvas.
- Assert every item has `reqLevel=200`, the expected job restriction, and the
  original nonzero upgrade slot count.
- Assert removed mechanism/restriction fields are absent.
- Assert all three String/Eqp tables contain exactly the selected names.
- Assert the five shoulder IDs remain absent.

