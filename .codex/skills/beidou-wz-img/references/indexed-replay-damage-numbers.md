# Indexed replay damage-number workflow

Use this workflow only when a skill's first client attack is followed by
server-scheduled replay attacks and the old client does not render the local
player's replayed `CLOSE_RANGE_ATTACK` damage lines. Do not apply it to ordinary
client-owned attacks or as a substitute for fixing targeting, timing, damage,
or hit effects.

## Evidence gate

Confirm the runtime path before editing:

1. The server sends the replay `CLOSE_RANGE_ATTACK (0xBA)` to the caster and
   other map characters.
2. The caster's local client rejects its own replay at the local-CID/remote-
   character lookup, while another player can render the replay's hit list.
3. The local fallback currently sends one ordinary `DAMAGE_MONSTER (0xF6)` per
   monster, which always uses native hit index `0` and therefore overlaps.

Do not force a local player object through the remote attack decoder. That path
has action/state side effects and is not a display-only API.

## Protocol and client bridge

Use `PacketCreator.indexedDamageMonsterNumber(oid, damage, hitIndex)` for local
display-only packets. Keep ordinary `damageMonster()` unchanged:

- `0x80..0x8E` in the `DAMAGE_MONSTER` direction byte represent native hit
  indices `0..14`.
- Every other direction value keeps native hit index `0` behavior.
- Preserve the raw signed damage value so the client's critical/sign marker is
  not lost.

`IndexedDamageNumberCompat.dll` must validate the exact 30-byte client span at
`0x0066C6CB`, then call the native number routine `0x006691D3` with the decoded
index. It must not read a skill ID, enter the remote-player path, or apply
damage. Load it from the diagnostics watchdog thread, outside `DllMain`.

## Timing template

The native player attack constructor at `0x0066B05E` schedules the default
multi-hit line as `baseTime + 120ms * hitIndex`; legacy Brandish/轻舞飞扬
`1121008` uses this default path. Therefore the shared server helper must:

1. Send hit index `0` immediately.
2. Schedule hit index `n` at `n * 120ms` for `n = 1..14`.
3. Send all monsters' same hit index in the same scheduled callback, so one
   replay tick remains synchronized across targets.
4. Capture the damage lists before scheduling and stop a callback when the
   character has changed maps.

Keep `120ms` as the generic default. A skill-specific interval is allowed only
when its verified source attack timeline requires it and overlapping replay
ticks would otherwise create concurrent indexed sequences. Record that source
evidence and keep the override at the skill call site; Dawn Warrior Galaxy Star
Burst `11121005` uses `60ms`, matching its TMS multi-attack cadence.

The helper only sends display packets. For each monster, calculate the decoded
total separately, call `aggroMonsterDamage()` once, and call
`MapleMap.damageMonster()` once. Never apply damage once per display line.

## Empty-cast damage template

For a duration or scheduled replay skill, an empty initial target list is not a
damage event and must not eagerly create a maximum-damage singleton template.
Keep the schedule alive and scan the current attack bounds on every tick. If a
tick still has no live target, return before creating a packet, damage-number
packet, aggro, or HP settlement. Only after a later tick finds at least one live
target may the handler create a fallback damage template, and that template
must contain one independently generated value per hit instead of copying one
fixed maximum into every hit slot. Generate this fallback for the current tick;
do not cache it across later ticks. A captured non-empty client damage template
continues to take precedence.

## Skill integration

Use an explicit local display mode in the handler:

- `NONE`: no caster-only compensation.
- `TOTAL`: preserve an existing single aggregate number.
- `INDEXED`: use the shared timed helper.

For a duration skill such as Dawn Warrior `11121012` (宇宙之花), the first
scheduled tick and every replay tick that needs caster-local numbers must use
`INDEXED`. Keep the skill's existing replay schedule, target collection,
attack packet broadcast, and one-time damage settlement unchanged.

## Verification and delivery

Before delivery, verify all of the following:

- Ordinary `DAMAGE_MONSTER` still writes marker `0`; indexed packets accept only
  hit indices `0..14`.
- The client executable bytes at the hook span still match the recorded 30-byte
  baseline; a mismatch aborts installation without patching.
- Static tests cover packet layout, signed damage preservation, timing constant,
  map-change cancellation, and the skill's `INDEXED` call site.
- Java 21 targeted tests, 32-bit DLL syntax checks, and `git diff --check` pass.
- The generated DLL is PE32, is built reproducibly twice, and is copied only
  after source/delivery hashes match.

Offline checks cannot prove old-client playback. On Windows/Winlator verify
launch/login, DLL load logs, first and later ticks, 120ms per-line cadence,
vertical stacking, critical styling, target death/map changes, repeated casts,
other-player view, and that HP decreases only once per replay target.

The project implementation record is maintained at
`docs/patches/indexed-replay-damage-numbers.md`.
