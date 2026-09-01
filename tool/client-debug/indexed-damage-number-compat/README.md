# Indexed damage-number compatibility DLL

`IndexedDamageNumberCompat.dll` gives server-replayed attacks a safe way to
reuse the old client's native per-hit vertical damage-number layout. It only
changes the local `DAMAGE_MONSTER` decoder at `0x0066C6CB`; it does not enter
the remote-player attack path, inspect a skill ID, change attack state, or
apply damage.

The packet's otherwise unused direction byte is the protocol boundary:

- `0x00..0x7F` and `0x8F..0xFF` keep the native hit index `0` behavior.
- `0x80..0x8E` map to native hit indices `0..14`.

The hook verifies all 30 original bytes before writing a five-byte jump and
aborts on another executable layout. `WzFileLogger.dll` loads this module from
its watchdog thread, outside the Windows loader lock.

Build only when new client artifacts are explicitly requested. This module and
the updated diagnostics loader are both required:

```bash
rtk bash tool/client-debug/indexed-damage-number-compat/build.sh
rtk bash tool/client-debug/wz_file_logger/build.sh
```

At runtime, `IndexedDamageNumberCompat.log` must contain:

```text
LOAD: Indexed Damage Number Compat v1
OK: indexed DAMAGE_MONSTER numbers enabled for markers 0x80..0x8E
```
