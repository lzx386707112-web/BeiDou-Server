# Cygnus V/VI Skill Compatibility DLL

`DawnWarriorSkillCompat.dll` is the unified runtime hook for the retained Dawn
Warrior skills, the Blaze Wizard V/VI compatibility range
`12121000..12121036`, and the retained Night Walker attack ranges
`14121003..08`, `14121014..17`, `14121027..28`, and `14121030..36`, plus
Thunder Breaker active skills `15121000`, `15121002..15121021` and server-only visual IDs
`15121022..15121033`. Dawn Warrior and Thunder Breaker continue through the native melee branch;
Blaze Wizard is routed through the native magic branch and its original flat
high-ID visual exit so the old client keeps direct `effect`, magic `hit`, and
damage-number paths. Night Walker uses the native ranged entry `0x009690E9` and
arms a skill-whitelisted MagicBullet trajectory hook for its migrated darts.
Version 41 also routes all migrated Explorer attack nodes through their legacy
melee, magic, or ranged constructors. Explorer Bowmaster, Marksman, Night Lord,
and Corsair active attacks use their migrated per-skill target limits and WZ
`lt/rb` ranges; their hidden replay stages remain renderable but cannot be put
on a hotkey. All 23 Explorer Origin video skills call the shared MCV player from
the same active dispatch before continuing through the native attack branch.
Thunder Breaker skills use the knuckle melee branch. `15121021` is the hidden Sea Dragon Spiral tick node,
so continuous hits do not replay the complete cast animation. The Lightning
Spear visual IDs `15121022..15121033` are accepted by the active-skill and
high-ID visual paths so server replay packets can render their standard
`effect`; keyboard dispatch remains capped at `15121021`, so players cannot
bind or actively cast the hidden IDs.
Blaze Wizard skills `12121025`
and `12121028` start their transparent MCV full-screen videos through
`BeiDouVideo.dll`; Night Walker uses the same path for `14121032` and `14121035`.
Thunder Breaker uses it for `15121016`, `15121017`, and `15121019`, keeping the
large multi-frame screen layers out of Skill.wz. Its active-skill hook queues
these videos until the next D3D8 Present, after the native melee constructor
has finished changing attack state.

The DLL patches the keyboard active-skill gate, the `DoActiveSkill` melee
dispatch, the high-ID visual tree, and the downstream Brandish-compatible
branches at runtime. Version 38 keeps the native requirement function intact,
including its MP/HP consumption and attack-state initialization, but no longer
classifies Thunder Breaker `15121000..15121021` as Hero Brandish in the four
downstream action, offset, state, and hit classifiers. Version 38 additionally
opens the server-only Lightning Spear replay range without making it keyboard-castable,
uses the old client's supported `alert5` action for every Lightning Spear stage,
and removes the unsupported Shark Torpedo compatibility path. Other attacks use
the same generic knuckle-melee path as native Thunder Breaker skill `15111004`. The
high-ID hook is required because `111210xx` leaves
the visual binary-search tree before the original Hero Brandish comparison.
It does
not patch the skill window, globally short-circuit native validation, or read/modify
`ijl15.dll`. The accompanying EXE patch only calls
`LoadLibraryA("DawnWarriorSkillCompat.dll")` during startup.

Build on macOS:

```bash
rtk bash tool/client-debug/dawn-warrior-skill-compat/build.sh
```

Install the tiny loader after building:

```bash
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py --dry-run
rtk python3 tool/scripts/patch-client/patch_dawn_warrior_skill_dll_loader.py
```

At runtime, inspect `clien/DawnWarriorSkillCompat.log`. A successful load
writes `LOAD: Cygnus/Explorer V-VI Attack Skill Compat vNN`
followed by the recognition-hook result. Version 40 routes the migrated Hero
`1121012..1121030` attack stages through the legacy Brandish active-skill,
visual, state and hit branches. Version 38 removes the unsupported
Thunder Breaker projectile compatibility path and keeps Lightning Spear on the
supported melee visual path. Version 33 also renders an active MCV
from the D3D8 Present hook when the field-layer marker is not drawn, so Origin
full-screen effects remain visible on clients whose Gr2D path skips the marker.
Version 31 removes the accidental
Brandish sword/axe classification from migrated Thunder Breaker attacks while
preserving native skill validation. Version 28 gives Merciless Winds ten
independently targeted native projectiles and cycles them across the selected
monsters. Version 27 removes the three retired
Wind Archer entries and keeps Mistral Spring on the full-screen MCV path. Version 25 adds Thunder Breaker's
melee/ranged split, skill-range target cap and three MCV mappings. Version 21 captures the selected monsters' body centers and assigns them
directly to consecutive Shadow Bite `MagicBullet` endpoints. Version 20 pairs the Shadow Bite stages' visual projectile counts with
their maximum target counts (`15/3/1`) while keeping damage-line counts independent. Version 19
caches the projectile layer's `rx/ry` dispatch identifiers and uses visibly wider Shadow Bite curves.
Version 18 hooks the old client's ranged skill-range classifier at `0x7666CB`,
so Shadow Bite uses its migrated `lt/rb` bounds instead of the normal throwing-star line. Version 17 forces the target collector at `0x678476` to use the migrated
Shadow Bite target limits and logs the number of targets actually selected. Version 16 hooks the native ranged multi-target classifier at `0x766722`,
so Shadow Bite enters the same target-array construction path as the old client's built-in multi-target
throwing skills. Version 15 preserves the Shadow Bite projectile window across its hidden
normal/Boss hit stages and re-arms it for both bat stages. Version 14 adds fixed converging arcs for the Shadow Bite bats and keeps
their flight time within `240..900ms`. Version 13 replaces the random Night Walker projectile modes with
skill-specific paths: Rapid Throw cycles through three fixed lanes and Silent Night uses alternating
homing arcs. It also adds Dominion's
MCV full-screen layer. Version 12 added ranged dispatch and the first Night Walker projectile runtime.
Version 11 extended the magic visual range
for hit-only replay stages; the video path intercepts the real
`Direct3DCreate8` lookup inside `Gr2D_DX8.dll`. After the diagnostics DLL is
loaded, the compatibility DLL re-chains its `LoadLibraryA` hook so the logger
cannot displace the early Gr2D interception. It does not create temporary D3D8
devices or retry against shared vtables after initialization; missing the real
device creation path disables MCV playback for that session without disturbing
ordinary rendering. The server sends a caster-only `FIELD_EFFECT` whose
`Map/Effect.img` node contains a signed `7x5` marker. Video rendering is
triggered when Gr2D draws that marker, reusing the same field-effect layer as
the previous large-Canvas implementation so hit effects, damage numbers, and
UI keep their native ordering. `Present` is no longer the video draw point. No
local `d3d8.dll` is used. This is the required path on Winlator/Mobox. The
video renderer uses the complete render-target dimensions instead of the
viewport left behind by the game, so full-screen effects are not clipped to a
smaller rectangle.
