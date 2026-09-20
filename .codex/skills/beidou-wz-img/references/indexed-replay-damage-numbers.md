# Caster-local replay damage numbers

Use this reference when a skill’s **first client-owned attack** shows native
player numbers, but **server-scheduled replay** `CLOSE_RANGE_ATTACK (0xBA)`
ticks do not show the same numbers on the caster.

This is not a targeting, timing, HP, or hit-effect fix. Do not apply it to
ordinary client-owned attacks.

Read this file completely before adding a hook, an F6 supplement, or a
`LocalDamageNumberMode` change.

## Two native constructors (do not mix)

| Path | Address | Look | When it is correct |
| --- | --- | --- | --- |
| Player / Brandish | `0x0066B05E` | 轻舞飞扬 `1121008` style; default cadence `baseTime + 120ms * hitIndex` | **Default for new skills** that must match the first half |
| Monster wrapper | `0x006691D3` | Different height/stacking; used by `DAMAGE_MONSTER (0xF6)` | Legacy only: already-shipped Dawn Warrior `INDEXED` skills |

`TOTAL` `damageMonster()` and `INDEXED` F6 (`0x80..0x8E` → `0x006691D3`) do
**not** match `0x0066B05E`. Do not use them to “copy the first half”.

Do **not** call remote decoder `0x009803AB` from a hook. Native `0xBA`
handling already reaches it. The working bridge only substitutes `CUserLocal`
at the failed lookup, then skips the two local action writes.

## Evidence gate (required before any edit)

1. First-half numbers come from a **client-owned** `0xBA` that the local
   player processes itself (constructor `0x0066B05E`).
2. Server already sends later ticks as `0xBA` to the caster **and** the map.
3. Local replay dies at `0x0097250B` → `call 0x00971709`: `CUserLocal` is not
   in the remote-user map; `esi == 0` at `0x00972512` jumps to `0x00972626`.
4. Another player can already render the same replay hit list.
5. Confirm whether the missing piece is numbers, target count, or both.
   Target count is a server collect problem; do not “fix” it with F6.

If step 1 is not `0x0066B05E`, stop. Do not copy the Brandish bridge.

## New skill: Brandish-identical numbers (default)

Follow these steps in order. Sword Illusion `1121020` (hidden `1121021` /
`1121022`) is the proven analogue.

### 1. Server: replay is `0xBA`, display mode is `NONE`

In `CloseRangeDamageHandler`:

- Call `scheduleTrackingCloseAttacks(..., applyOriginalFirst, NONE)`.
- Keep a verified TMS replay schedule. Fullscreen MCV ultimates keep the
  skill’s current stage times and WZ `attackCount` for the video duration.
- Do **not** pass `LocalDamageNumberMode.INDEXED` or `TOTAL`.
- Do **not** call `damageMonster()` / `indexedDamageMonsterNumber()` /
  `showIndexedDamageNumbers()` for this skill.
- Damage settlement stays `aggroMonsterDamage()` + `map.damageMonster()`
  **once per monster per tick**, from the replay hit list.

`applyOriginalFirst`:

- `true` only when the opening client packet already has the correct mob
  list (same box and `mobCount` as the skill).
- `false` when the client action is a small analogue (Sword Illusion uses
  `brandish1` / `1121008` `mobCount=3`). Then **every** tick, including the
  first slash, must server-collect.

### 2. Server: collect the skill box, not feet and not the first packet

Each replay tick:

- Use the **cast skill** `StatEffect` (`originalEffect`) for `lt`/`rb` and
  `mobCount`, not a tighter hidden-skill box, unless evidence says otherwise.
- Select with `isWithinAttackBox(...)` (monster bbox ∩ skill box; try
  packet direction, stance, and current facing).
- Cap at the skill `mobCount` (Sword Illusion: **8**).
- Do **not** use `attackBounds.contains(monster.getPosition())` (feet-only).
- Do **not** reuse `attack.allDamage` when that list is the Brandish-sized
  client packet.

Copy the captured per-hit template onto every collected monster. If this
skill is server-authoritative and the template is empty, the existing
fallback template is allowed. Dawn Warrior duration skills must still skip
empty templates (see legacy section).

### 3. DLL: allowlist the hidden replay skill IDs

Edit only `tool/client-debug/indexed-damage-number-compat/IndexedDamageNumberCompat.cpp`.

Keep the three existing hooks. **Add new work only as extra `cmp` skill IDs
in `HookLocalCloseRangeLookup`.** Do not add a fourth hook, do not call
`0x009803AB`, and do not change the F6 hook unless the EXE bytes moved.

Lookup hook (`0x00972512`, original `85 F6 0F 84 0C 01 00 00`):

1. If `esi != 0`, continue at `0x0097251A` (normal remote user).
2. Peek `CInPacket`: `eax = [edi+8] + [edi+0x14]`.
3. Require `[eax+1] == 0x5B` and `[eax+2] != 0` (matches
   `PacketCreator.addAttackBody`: packedCount, `0x5B`, skilllevel, skill).
   4. Compare `[eax+3]` (u32 skill id) to the **hidden replay IDs**, not the
   visible cast ID. Current allowlist: `0x00111AFD` (`1121021`),
   `0x00111AFE` (`1121022`), `   0x00111B00` (`1121024`), `0x0012A19D`
   (`1221021`), `0x0012A19E` (`1221022`), `0x0012A1A7` (`1221031`),
   `0x0014283B` (`1321019`), `0x00142842` (`1321026`).
5. On match: `esi = [0x00BEBF98]` (`CUserLocal`). If null, skip.
6. Otherwise jump `0x00972626` (drop packet), same as stock client.

Required skips (already installed; do not remove when adding a skill):

- `0x0098046E`: if the decoded user is `CUserLocal`, skip `SetMoveAction`
  (`0x009804BB`); else original `lea esi, [eax+0x88]` → `0x00980477`.
- `0x009803E5`: if `esi` is `CUserLocal`, skip `[esi+0x2AE0] = al`; else
  write and continue `0x009803EB`.

These skips are what make entering the native `0xBA` decoder safe. Without
them the local player restarts Brandish.

Load from the diagnostics watchdog thread, not `DllMain` work. Image base
must be `0x00400000`. Every hook span must match recorded original bytes or
install aborts.

### 4. Tests and build

Update `tool/client-debug/indexed-damage-number-compat/test_indexed_damage_number_contract.py`:

- New replay IDs appear as `0x00......` in the DLL source.
- The `CLOSE_RANGE_ATTACK` handler block for the **cast** skill (search
  `} else if (attack.skill == ...)` , not an earlier `==` in collect code)
  contains no `INDEXED`, `TOTAL`, or `damageMonster(`.
- Existing EXE byte spans still match.

Rebuild with the checked-in script, twice, require identical SHA-256:

```bash
tool/client-debug/indexed-damage-number-compat/build.sh
rtk python3 tool/client-debug/indexed-damage-number-compat/test_indexed_damage_number_contract.py
rtk git diff --check
```

Do not rebuild the server JAR unless the user asks. Deliver only this task’s
changed runtime files (`IndexedDamageNumberCompat.dll` if the allowlist
changed). Java-only targeting changes have nothing to copy until a JAR is
requested.

### 5. In-game checks this file cannot prove

Launch, login, DLL `LOAD`/`OK` in `IndexedDamageNumberCompat.log`, first
tick and later ticks, 120ms line cadence, Brandish-identical style,
critical sign bit, up to `mobCount` monsters in the skill box (both
facings), other-player view, map change, repeat cast. HP drops once per
replay target per tick.

## Fullscreen MCV ultimates (required template)

Use this section when the skill is a **fullscreen MCV 大招**: a full-screen
video layer (`showEffect` / `Data/Video/*.mcv`). Keep the video. Do **not**
replace the skill’s current hit stages with a 500ms full-map pulse. Do **not**
use F6 `INDEXED`/`TOTAL` for caster numbers, including Dawn Warrior video ults
when they are converted.

The point of these skills is: during the MCV duration, keep attacking on the
**current stage times** (`multiAttackInfo` / existing Java arrays) with the
**current WZ `attackCount`**, and show **native player/Brandish numbers**
(`0x0066B05E`) via hidden-ID `0xBA` replay.

Proven analogue: 圣剑降临 `1121023` / hidden replay `1121024`.

| Skill | Cast ID | Hidden replay IDs | MCV duration |
| --- | --- | --- | --- |
| 圣剑降临 | `1121023` | `1121024` (`0x00111B00`) | 7020ms |
| 圣域展开 | `1221020` | `1221021` / `1221022` | 5340ms |
| 圣狮之主 | `1221030` | `1221031` (`0x0012A1A7`) | 2820ms |
| 灭世永恒之枪 | `1321018` | `1321019` (`0x0014283B`) | 6180ms |
| 黑暗契约 | `1321025` | `1321026` (`0x00142842`) | 2460ms |

Do not allowlist the visible cast ID.

### Steps (do in order)

1. Keep `showEffect` for the MCV. Do not guess a new hit clock.
2. Keep the existing slash/finish (and field, if already shipped) time arrays.
   Opening stage `applyOriginalFirst=true`; later hidden stages `false`.
3. Replay packets use the **hidden** ID so `IndexedDamageNumberCompat` can
   show local `0xBA` numbers. Opening-stage `attackCount`/`mobCount` come from
   the **visible** WZ node; finish-stage counts come from that hidden node.
4. `scheduleTrackingCloseAttacks(..., NONE)`. Empty client templates may use
   the visible-skill fallback. Collect with the visible skill box, not a
   rewritten 500ms full-map pulse.
5. Settle HP once per monster per tick (`aggroMonsterDamage` +
   `damageMonster`).
6. Add only the hidden replay IDs to `HookLocalCloseRangeLookup`. Keep the two
   local action skips. Rebuild `IndexedDamageNumberCompat.dll` twice.
7. Contract tests lock: TMS stage arrays present, WZ `attackCount` unchanged
   from the skill node, no `INDEXED`/`TOTAL`/`damageMonster(` in the cast
   `handlePacket` block, and the hidden hex IDs in the DLL source.

### Do not

- Replace stage times with `intervalTimes(500, 500, duration)`.
- Collapse WZ `attackCount` to 1 to work around packet occupancy.
- Mix a 500ms full-map pulse with leftover TMS stages.
- Use the visible cast ID as the `0xBA` replay skill.
- Use F6 to imitate Brandish numbers.

## Forbidden (already failed)

- `TOTAL` F6 aggregate numbers.
- `INDEXED` F6 → `0x006691D3` to imitate Brandish.
- Calling `0x009803AB` from the DLL.
- Substituting `CUserLocal` for **every** failed `0xBA` lookup (not
  skill-filtered).
- Allowlisting a skill without the two local action skips.
- Treating “packet parses” or “other players see hits” as proof that the
  caster sees `0x0066B05E` numbers.

## Legacy: F6 `INDEXED` (do not use for new Brandish-style skills)

Already shipped: 宇宙之花 `11121012`, 银河星爆 `11121005` (60ms override),
全蚀之力 `11121006`, 灵魂蚀日 `11121008`.

Those skills keep `LocalDamageNumberMode.INDEXED` and
`showIndexedDamageNumbers` **until** they are converted as fullscreen MCV
ultimates. A converted video ult must drop `INDEXED` and follow the MCV
template above (current stages + WZ `attackCount` + hidden `0xBA` numbers).

- `PacketCreator.indexedDamageMonsterNumber(oid, damage, hitIndex)`
- direction `0x80..0x8E` → native index `0..14`; other values stay index `0`
- helper sends index `0` immediately, then `n * 120ms` (or the verified
  skill override)
- F6 hook at `0x0066C6CB` (30-byte baseline) still calls `0x006691D3` only
- empty client damage template: skip the tick; no `500000` fallback

`TOTAL` remains only for older aggregate-number skills that already used it.

## Implementation files

- DLL: `tool/client-debug/indexed-damage-number-compat/IndexedDamageNumberCompat.cpp`
- Build: `tool/client-debug/indexed-damage-number-compat/build.sh`
- Output: `clien/IndexedDamageNumberCompat.dll`
- Server schedule / collect: `CloseRangeDamageHandler`
- Box test: `AbstractDealDamageHandler.isWithinAttackBox`
- F6 helper: `AbstractDealDamageHandler.showIndexedDamageNumbers`
- Record: `docs/patches/indexed-replay-damage-numbers.md`
