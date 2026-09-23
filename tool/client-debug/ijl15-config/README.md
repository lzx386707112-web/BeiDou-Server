# ijl15 config loader

This incremental patch keeps the existing `clien/ijl15.dll` compatibility
hooks and adds one startup loader for the network settings in `config.ini`:

```ini
ServerIP_Address=127.0.0.1
serverIP_Port=19696
```

Both key names are matched without ASCII case sensitivity. Missing, empty, or
invalid values retain the DLL's existing defaults; the port must be in
`1..65535` and the address value is limited to 63 bytes.

Build and verify on macOS:

```bash
rtk bash tool/client-debug/ijl15-config/build.sh
rtk python3 tool/client-debug/ijl15-config/test_contract.py
```

The builder adds or refreshes only the `.bdcfg` PE section and the verified
seven-byte initialization trampoline. Repeating the build is byte-identical.

To distinguish a client routing problem from a login-service failure, send an
intentionally invalid v83 login request and expect an immediate `LOGIN_STATUS`
response:

```bash
rtk python3 tool/client-debug/ijl15-config/probe_login.py HOST PORT
```

The probe never uses a real account. A handshake followed by a response timeout
means the endpoint accepted the client connection but did not finish processing
the login request.
