# Map, NPC, mob, and boss workflow

Read this reference when adding or changing maps, `life` nodes, NPCs, mobs,
bosses, or their String records.

## Resolve the complete resource chain

Before editing, identify:

- client map IMG and matching server map XML;
- client/server NPC or Mob resource;
- client `String/Npc.img` or `String/Mob.img` record;
- server and translated String XML records used by the runtime;
- scripts, drops, portals, reactor/event logic, and quest references;
- a working legacy map life node and a working legacy NPC/mob with the same
  behavioral shape.

Do not infer coordinates, footholds, layer, movement type, boss behavior, or
resource paths from names alone.

## Migrating maps: numeric gaps, ropes, leftover modern fields

These failures are usually in-map (missing geometry, crash while walking a
layer, ropes that never appear). They are not the Bishop-style startup
“incorrect game data” unless the IMG was also full-serialized.

Implement with incremental record edits. Do not parse-and-reserialize an
existing map. Proven generators:

- `tool/scripts/migration/repair_monster_park_late_course_obj_gaps.py`
- analogue densify/fill: `tool/scripts/patch-client/repair_arcana_450005242_obj_gaps.py`

### Numeric `obj` / `back` gaps (节点断层)

**Problem.** The old client walks `back` and each `<layer>/obj` by numeric
child name from `0` through `max(name)`. TMS maps and later repairs often
leave holes:

- modern `connect` objects used high `l1` folders; stripping them without
  renaming siblings leaves `23` then `25` (missing `24`);
- some layers start at `102` or `104` with no `0..n-1` (leading gap).

The file still parses. The client then skips, crashes, or drops that layer.

**Solution.**

1. Collect digit names. Missing IDs are
   `[i for i in range(max + 1) if i not in names]`.
2. Fill each contiguous hole by **raw-inserting** projected clones of the
   nearest sibling (`insert_property_records_before` on the client IMG;
   matching XML insert). Copy only legacy fields (`oS/l0/l1/l2/x/y/z/f/zM`
   for obj; the existing `back` field set for backgrounds).
3. Preserve remaining object bytes and sibling order. Do not rename every
   later object just to densify names (that rewrites the whole parent).
4. Patch the matching server map XML the same way. Re-parse; require no
   truncation or warnings; prove insert scope; run the filler twice with
   identical hashes.

A large leading gap (`0..103`) duplicates the template object many times.
That is binary-safe but can look like repeated scenery in-game. State that
risk. Do not apply this fill to the entire GMS world “because a scanner
found holes”; scope to maps this migration actually rewrote.

### `connect` ropes and ladders

An entry is `l0` (folder `rope`/`ladder`), `l1` (style), `l2` (piece). The client
walks `connect/{l0}/{l1}/{l2}` literally, so **the only thing that makes a rope
vanish is a style or piece index that does not exist in
`clien/Data/Map/Obj/connect.img`.** That asset is complete: rope styles `0`-`82`,
ladder styles `0`-`87`, and untouched GMS towns already use `l1` up to `43`
(rope, 12 971 objects) and `67` (ladder, 7 503 objects).

**Correction (2026-09-29).** The earlier rule here — "remap `l1` outside
`{0,1,2,3,4}` to `0` and clamp `l2` to `0-4`" — is wrong on both counts. It was
derived from `migrate_arcane_river_expansion.downgrade_connect_nodes()`, which
*synthesises* display nodes from `ladderRope` collision data and therefore had
to pick a style; picking `0` there says nothing about maps whose real style is
known. Applying the same flattening to a source map that carries its own
`l1`/`l2` keeps TMS's piece indices but swaps the style, and because style `0`
pieces are 49/30/30/120/49 px while TMS picked its indices against the heights of
its own style (`8`, `22`, `45`, `60`, `65`, `73`, …), the pieces stop tiling and
the rope renders **with holes** — what players report as "绳子断断续续".

**Solution.**

- Keep the source `l1`/`l2` whenever `connect/{l0}/{l1}/{l2}` resolves in the
  client's `connect.img`. Verify the piece count, not just the style.
- Only when the style or piece is missing, fall back to the legacy flat mapping
  (`l1="0"`, piece clamped to the real piece count of style `0`).
- Match source and client connect objects by **physical placement**
  `(layer, x, y, z, l0)`, never by the numeric child name. The two trees order
  their `obj` children differently, so name-based pairing silently compares
  unrelated ropes.
- Same-length string mutate on the existing records; mirror in XML. A two-digit
  value grows the record by one byte — `mutate_img` rebases the string-block
  references and the enclosing size fields, then re-`scan_img`s the result.
- On maps this task migrated, strip leftover modern object fields
  (`spineAni` as a whole object, `questex` / `tags` / `timeScale` as
  fields). Do not mass-strip `tags` from unmodified GMS towns.
- After connect edits, re-scan for numeric gaps and fill them.

**Measuring rope continuity.** For each chain grouped by `(layer, l0, x)`, take
every piece's `height` and `origin.y`, convert to a span
`[y - origin.y, y - origin.y + height]` (`origin` is a `WzVectorProperty` whose
`.value` is an `(x, y)` tuple), sort the spans and sum the uncovered intervals.
A correct rope reports `0`. Residual holes can be legitimate: two separate short
ropes at the same `x` in one layer are merged by the grouping, so always compare
against the source tree's own number before calling it a defect.

Worked example — Seed Tower 1-20F, 297 values across
`992002000/992003000/992011000/992016000/992017000/992019000`
(`repair_seed_tower_20f_ropes.py`): uncovered pixels went 639/1435/0/858/895/114
to 0/0/0/450/0/1, where `450` is what the TMS source itself measures for
`992016000`.

### Contract tests

`tool/scripts/migration/test_monster_park_late_course_obj_gaps.py` and a
second generator pass with `maps_needing_repair() == []`. For rope work also
assert, per connect object, that `connect/{l0}/{l1}/{l2}` resolves in
`connect.img` — not that `l1` sits in some fixed set. In-game: enter the map,
climb ropes/ladders, look for missing or duplicated objects.

## Existing map IMG

Never full-serialize an existing map to add a spawn. Scan its real `life`
record order, choose an unused child name, and raw-insert only the new record.
Update the matching server XML block incrementally.

Project the life node from a working analogue and verify at least:

- `type` (`n` or `m`) and string-form `id` where the target contract uses it;
- `x`, `y`, `fh`, `cy`, `rx0`, `rx1`;
- `f`, `hide`, and `mobTime` or other required spawn controls;
- portal/event linkage and spawn timing when applicable.

After insertion, prove every pre-existing `life` record is byte-for-byte
unchanged and its relative order is preserved. Reopen the map and verify the
new node values exactly.

## Map `life` is correct but nothing spawns (instance / PQ maps)

Symptom: client IMG and server XML both list many `life` mobs, but in game
only the script-spawned ones appear. The map data is not the bug.

- The periodic mob respawn (`RespawnTask` -> `ch.getMapFactory().updateMaps()`
  -> `MapleMap.respawn()`) only walks the **channel** `MapManager`.
- An event instance builds its own `MapManager` (`EventInstanceManager`), so
  its maps never receive that tick.
- `resetPQ()` on floor/stage entry runs `clearMapObjects()` ->
  `killAllMonsters()`, then `instanceMapFirstSpawn()`, which respawns **only
  `mobTime == -1`** spawn points. Rooms whose `life` uses `mobTime: 0` are
  wiped and stay wiped.

Every working PQ script refills itself, e.g. `HenesysPQ.js`:

    function respawnStages(eim) {
        eim.getInstanceMap(910010000).instanceMapRespawn();
        eim.schedule("respawnStages", 15 * 1000);
    }

Checklist: `grep instanceMapRespawn` in the event script. If it is missing
while the map's `life` uses `mobTime: 0`, that is the bug. Add a
self-rescheduling `eim.schedule` that calls `instanceMapRespawn()`, plus one
immediate call right after the floor warp so the room starts populated.
`mobTime: -1` rooms are deliberately one-shot and need nothing; rooms with no
`life` mobs are inert (numShouldSpawn <= 0).

In-game verification: GM `!debug mobsp` lists every spawn point with
总刷怪点 / 已刷怪 / 可刷怪, and `!debug map` prints the live monster count.

### Editing a clear condition in these PQ scripts

These scripts clear a floor from two places, and a naive edit leaves a bypass:

- a floor-specific branch inside `monsterKilled()` (e.g. `if (id==9309131) markClear(eim)`);
- the generic tail of `monsterKilled()`:
  `if (goals[f] && f!=3 && f!=13 && f!=18 && num(eim,"score")>=goals[f]) markClear(eim)`.

When a floor must satisfy **several** conditions, do not just add the extra
condition to the floor branch — exclude that floor from the generic line
(`f!=1`) and evaluate the whole rule in one helper (`floor1Check(eim)`) called
from every contributing event, so the order of the conditions never matters.
Also add any new counter key to the reset array in `enterFloor()`, or it leaks
across floors. Boss/objective mobs usually do **not** increment `score`.

## NPC and mob resources

A genuinely new standalone `Npc/<id>.img` or `Mob/<id>.img` may be serialized
from a reviewed compatibility projection. An existing NPC or Mob IMG must use
record-level edits.

When migrating TMS animation data:

- resolve UOL/outlinks and materialize Canvas data to GMS ARGB4444;
- preserve frame names/order, delays, origins, z-order, dimensions, alpha, and
  movement/action structure needed by the old client;
- compare boss attacks, hit/death states, stats, and movement with a compatible
  legacy mob rather than copying unsupported modern nodes;
- decode all affected visible Canvas frames, not only their headers.

Add String records incrementally. Do not regenerate all of
`String/Npc.img` or `String/Mob.img` for one name.

## Migrating mobs: ranged ballistic attacks

**Problem.** Modern TMS mobs (especially Arcane River `864*`) can ship
`attackN/info/ball` and `hit` canvases without the old-client projectile
fields. The attack then has no ballistic type, no flight speed, or a hit
node that never attaches. Melee `firstAttack` without `ball` is a
different contract; do not invent a `ball` node.

Working analogue: `8641002` `attack1/info` —

- `range`, `ball`, `hit`
- `type=2` (projectile)
- `attackAfter`
- `bulletSpeed` (300 on that analogue; some Lucid-era mobs use 400)
- `hit/attach=1`

Known incomplete shapes: missing `type`; `type` present but not `2`;
missing `bulletSpeed`; `hit` present without `attach`. Example that had
`ball`/`hit`/`attackAfter` but no `type` or `bulletSpeed`: `8644412`.

**Solution.**

1. After cloning or editing a mob, scan every `attack*` whose `info`
   contains `ball`.
2. On an **existing** Mob IMG, insert only the missing scalars
   (`type=2` before `attackAfter` when that sibling exists; append
   `bulletSpeed` and `hit/attach=1`). Do not full-serialize the mob.
3. Keep existing `ball`/`hit` canvases, delays, and attack timing.
4. Mirror the same nodes in `gms-server/wz/Mob.wz/<id>.img.xml`. Do not copy
   Mob XML into `wz-zh-CN`.
5. Prefer speeds from
   `LEGACY_BALLISTIC_ATTACKS` in
   `tool/scripts/migration/migrate_arcane_river_expansion.py`; default
   `300` when the table has no value.
6. Reuse `repair_ballistic_mob` /
   `iter_incomplete_ballistic_attacks` in
   `migrate_twilight_perion_monster_park.py`. Require a second run with
   an empty leftover list.

Contract: `tool/scripts/migration/test_arcane_river_ballistic_contract.py`
(and the `450001014` / `8641002` analogue checks). Offline parse cannot
prove Winlator projectile flight; remaining in-game checks are cast,
visible bolt, impact attach, and no stuck attack animation.

## Server and runtime contract

Verify server NPC/Mob XML, map XML, NPC/quest/event scripts, stats, drops,
respawn/boss rules, and any Java constants or handlers. A client animation file
does not make the server spawn or control the entity.

## Map/entity verification

- Raw-record audit for every existing Map/String/NPC/Mob IMG touched.
- Independent parse with no truncation/warnings.
- Exact life-node value and sibling-order assertions.
- Canvas format and visible-pixel decode audit.
- Server XML semantic diff limited to approved IDs/paths.
- Script syntax and relevant server contract tests.
- Static reopen of each affected IMG, with exact resource/spawn-path assertions;
  do not create a temporary WZ unless the user explicitly requests packaging.
- For migrated maps: `back` and every layer `obj` have names `0..max` with
  no holes; every `connect` resolves as `connect/{l0}/{l1}/{l2}` inside
  `Map/Obj/connect.img`; `spineAni` /
  `questex` / `tags` / `timeScale` are gone on maps this task rewrote.
- For migrated mobs with `ball`: `type=2`, `bulletSpeed` present,
  `hit/attach=1` when `hit` exists.
