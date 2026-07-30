# Dawn Warrior Skill Compatibility DLL

`DawnWarriorSkillCompat.dll` is the unified runtime hook for the retained Dawn
Warrior skills, the Blaze Wizard V/VI compatibility range
`12121000..12121036`, and the retained Night Walker attack ranges
`14121003..17`, `14121027..28`, and `14121030..36`. Dawn Warrior continues through the native melee branch;
Blaze Wizard is routed through the native magic branch and its original flat
high-ID visual exit so the old client keeps direct `effect`, magic `hit`, and
damage-number paths. Night Walker uses the native ranged entry `0x009690E9` and
arms a skill-whitelisted MagicBullet trajectory hook for its migrated darts.
Blaze Wizard skills `12121025`
and `12121028` start their transparent MCV full-screen videos through
`BeiDouVideo.dll`; Night Walker uses the same path for `14121032` and `14121035`.

The DLL patches the keyboard active-skill gate, the `DoActiveSkill` melee
dispatch, the high-ID visual tree, and the downstream Brandish-compatible
branches at runtime. The
high-ID hook is required because `111210xx` leaves
the visual binary-search tree before the original Hero Brandish comparison.
It does
not patch the skill window, short-circuit native validation, or read/modify
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
writes `LOAD: Dawn Warrior/Blaze Wizard/Night Walker Skill Compat v15` followed by the
recognition-hook result. Version 15 preserves the Shadow Bite projectile window across its hidden
normal/Boss hit stages and re-arms it for both bat stages. Version 14 adds fixed converging arcs for the Shadow Bite bats and keeps
their flight time within `240..900ms`. Version 13 replaces the random Night Walker projectile modes with
skill-specific paths: Rapid Throw cycles through three fixed lanes, Quintuple Throw keeps the
native straight flight, and Silent Night uses alternating homing arcs. It also adds Dominion's
MCV full-screen layer. Version 12 added ranged dispatch and the first Night Walker projectile runtime.
Version 11 extended the magic visual range
for hit-only replay stages; the video path first
intercepts the real `Direct3DCreate8` lookup inside `Gr2D_DX8.dll`; if Gr2D has
already initialized, it patches the shared D3D8 `Present`, `SetTexture`, and
draw tables through a temporary device and attaches the active game device on
its next frame. The server sends a caster-only `FIELD_EFFECT` whose
`Map/Effect.img` node contains a signed `7x5` marker. Video rendering is
triggered when Gr2D draws that marker, reusing the same field-effect layer as
the previous large-Canvas implementation so hit effects, damage numbers, and
UI keep their native ordering. `Present` is no longer the video draw point. No
local `d3d8.dll` is used. This is the required path on Winlator/Mobox. The
video renderer uses the complete render-target dimensions instead of the
viewport left behind by the game, so full-screen effects are not clipped to a
smaller rectangle.
