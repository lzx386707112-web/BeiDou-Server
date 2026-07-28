# Dawn Warrior Skill Compatibility DLL

`DawnWarriorSkillCompat.dll` lets the old 32-bit `BeiDou.exe` display and cast
the remapped Dawn Warrior skills `11121000..11121009`.

The DLL patches the skill-window and Brandish-compatible melee branches at
runtime. It does not read or modify `ijl15.dll`. The accompanying EXE patch
only calls `LoadLibraryA("DawnWarriorSkillCompat.dll")` during startup.

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
writes `OK: Dawn Warrior 11121000-11121009 compatibility hooks installed`.
