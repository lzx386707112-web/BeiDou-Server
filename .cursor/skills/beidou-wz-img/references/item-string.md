# Item, String, and drop workflow

Read this reference for task items, icons, String entries, Item XML, and drop
migrations.

## Item record mapping

Resolve the actual TMS source record and both client/server destinations. For
Etc items in this project, verify rather than assume the common mapping:

- client/server item record under `Item/Etc/0403.img` may be named
  `0<item-id>`;
- String record under `String/Etc.img/Etc` uses the plain numeric ID;
- server String data may exist in both `gms-server/wz` and
  `gms-server/wz-zh-CN`.

Inspect neighboring legacy records for required `info`, price/slot/quest flags,
icon structure, and sibling placement. Do not infer the container or padding
only from the numeric ID.

## Incremental insertion

For an existing Item or String IMG:

1. Scan the parent record order and verify the proposed anchor exists.
2. Clone only approved source records.
3. Materialize Canvas payloads and convert them to GMS ARGB4444.
4. Insert raw records before the selected anchor; never rewrite the full IMG.
5. Apply matching server XML/String additions incrementally.
6. Verify all legacy siblings retain their raw bytes and relative order.

For `icon` and `iconRaw`, require `format=1`, `format2=0`, dimensions greater
than an intentional placeholder, successful decode, and visible pixels.

## Drops and task consumption

Trace each item's complete acquisition and consumption path:

- installed mobs and maps that can supply it;
- task objective ID/count;
- completion action with the corresponding negative count or scripted removal;
- SQL/table uniqueness and idempotent migration behavior;
- `questid` restriction and evidence-backed chance/quantity.

Do not add drops for unavailable mobs. Do not make quest-only items global.
Avoid duplicate migration rows and verify a repeated migration produces the
same final contract.

## Item/String verification

- Client item and String records both exist at the exact expected paths.
- Server Item and all required String XML trees agree.
- Raw-record changes are limited to approved item/String roots.
- Every affected Canvas is decoded and visible.
- Task checks, item removal, scripts, and drop rows use identical IDs/counts.
- Statically reopen the affected Item and String IMG files, resolve names, and
  decode icons; do not create a temporary WZ unless the user explicitly
  requests packaging.
