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
