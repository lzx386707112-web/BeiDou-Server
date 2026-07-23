# BeiDou fifth-job runtime trace

`BeiDouVSkill.dll` is a diagnostic-only DLL for the imported ShenShuo
`1112/1512` skills. It does not create a panel, handle mouse input, modify a
skill result, or send packets.

At startup it verifies and wraps four existing direct calls:

- keyboard generic-active path -> `CUserLocal::DoActiveSkill`
- `DoActiveSkill` -> native skill data/level lookup
- `DoActiveSkill` -> native skill validation routine
- `DoActiveSkill` -> native close-range attack routine

Every wrapper calls the original target with the original arguments and return
convention. Only the 40 imported skill IDs are logged. The log is written to
`clien/beidou_vskill_trace.log`, with `%TEMP%` as a fallback when the client
directory is not writable.

Build from macOS:

```bash
rtk bash tool/client-vskill/build_mingw.sh
```

Install the DLL loader in `BeiDou.exe`:

```bash
rtk python3 tool/scripts/patch-client/patch_vskill_client.py --dry-run
rtk python3 tool/scripts/patch-client/patch_vskill_client.py
```

Expected startup line:

```text
Trace hooks: DoActiveSkill=1 SkillLookup=1 Validation=1 Melee=1.
```

Press one imported skill once, close the client, and inspect the trace in this
order. A missing line identifies the first native gate that was not reached:

```text
DoActiveSkill entry
Skill lookup
Validation
Melee entry
Melee return
DoActiveSkill return
```
