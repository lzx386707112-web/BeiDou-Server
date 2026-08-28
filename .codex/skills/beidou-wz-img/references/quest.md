# Quest IMG and Workbench workflow

Read this reference for Quest records, task scripts, quest items/drops, and the
Workbench task platform.

## Complete quest contract

Audit all four client files and matching server XML:

- `clien/Data/Quest/Act.img`
- `clien/Data/Quest/Check.img`
- `clien/Data/Quest/QuestInfo.img`
- `clien/Data/Quest/Say.img`
- `gms-server/wz/Quest.wz/{Act,Check,QuestInfo,Say}.img.xml`
- `gms-server/wz-zh-CN/Quest.wz/...` when used by the platform/runtime
- `gms-server/scripts-zh-CN/quest/<server-id>.js` when scripts are referenced
- the offering NPC script, referenced item resources, mob/map availability,
  quest-limited drops, and runtime quest-count routing

Check start/end NPCs, prerequisite quest IDs/states, level, repeat interval,
mob/item objectives, start/end scripts, rewards, item consumption, dialogue,
area, descriptions, and task-offering eligibility.

## Signed server IDs versus client roots

For this old client, a server quest ID in signed 16-bit range maps to the
client's unsigned root:

```text
-32768 <= server_id < 0  -> client_id = server_id + 65536
32768 <= client_id <= 65535 -> signed alias = client_id - 65536
```

Server XML and scripts keep the signed ID when that is the established server
contract. Client Quest IMG top-level roots use the positive/unsigned ID. Never
write a negative client root for these IDs.

Before create, save, or delete, scan all four client files. If the positive root
and signed alias both exist, reject the operation and repair from a known-good
baseline; do not silently choose one. Verify zero negative top-level roots and
zero positive/negative alias pairs after changes.

Workbench must route client mutations through
`quest_manager.app._client_quest_record_names` and `_replace_img_record`.
Create/edit/delete tests must prove:

- server XML retains the signed ID;
- all client files use the unsigned ID;
- a second identical save is byte-for-byte idempotent;
- delete removes the unsigned client record and signed server record;
- collision detection rejects simultaneous aliases;
- unrelated raw records remain unchanged.

## Building quest records

Read the actual TMS `Quest/QuestData/<positive-id>.img`. Do not copy the entire
modern record. Build a compatibility projection using working legacy quests:

- `QuestInfo`: only fields supported and required by the old client.
- `Check/0`: start NPC, minimum level, interval, prerequisites, and start script.
- `Check/1`: end NPC, objectives, ordering, and end script.
- `Act/0` and `Act/1`: compatible start/end actions, rewards, and negative item
  counts for consumed collection items.
- `Say`: supported dialogue tree, preserving the required branch structure.

Validate nested prerequisite/objective IDs against the proven client and server
conventions; root-name mapping alone does not prove nested values are correct.
Modern fields such as transfer or navigation controls must not be copied unless
a working old-client analogue proves support.

For each IMG, derive the insertion anchor from its real baseline order. Confirm
the anchor exists before generating and assert the intended task range remains
contiguous without moving protected siblings.

## Quest items and drops

For every collection task, verify the item exists in client Item/String and
server Item/String resources, the completion action removes the exact count,
and at least one available monster has a quest-limited drop. Confirm the mobs
actually spawn on installed maps. Do not add a global drop when the item should
be limited by `questid`.

For virtual TMS mob IDs used to combine kill counters, add and test explicit
server routing from each installed real mob ID. Do not substitute IDs merely
because names look similar.

## Quest-specific verification

- Compare all four IMG raw record maps to the working baseline.
- Existing records may differ only inside explicitly approved replacement
  roots; new records may appear only inside explicitly approved additions.
- Preserve protected top-level order after filtering approved additions.
- Parse all four files independently with no warnings.
- Assert every approved quest exists in all four client and server stores.
- Assert client roots are positive and server IDs remain signed as intended.
- Syntax-check offering NPC and quest scripts and run targeted quest contracts.
- Run Workbench regression tests after any task-platform change.
