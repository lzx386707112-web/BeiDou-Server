# Shared WZ/IMG method

This is the project-specific `wzskill.md` playbook. It applies to all client
resource types; use the format-specific reference for the exact contract.

## 1. Establish evidence before edits

Run all shell commands through `rtk`.

1. Read `rtk git status --short`. Existing modifications and untracked files
   belong to the user.
2. Read the relevant generator, contract tests, migration notes, runtime logs,
   screenshots/videos, and last failure report.
3. Separate startup “incorrect game data” failures from in-game visual,
   targeting, timing, server logic, and drop problems.
4. Identify the last known working artifact. Do not assume `HEAD` is good; use
   `HEAD`, `HEAD^`, a backup, or another ref only when evidence identifies it.
5. Record:
   - exact files and property paths allowed to change;
   - source region/key and target region/key;
   - expected sibling placement;
   - semantic outcome and binary invariants;
   - checks that constitute success.

For a Git binary baseline, use raw plumbing, never filtered binary stdout:

```bash
rtk proxy sh -c 'git cat-file blob HEAD:clien/Data/Quest/Act.img > /tmp/baseline-Act.img'
```

Use an exact task-specific temporary path and remove only that path afterward.

## 2. Choose a binary-safe technique

For an existing client IMG, prefer these techniques in order:

1. Same-length in-place scalar or string-payload edit when representation and
   encoded length are proven compatible.
2. Replace one raw property record with
   `wzpy.incremental_img.replace_img_record` or `mutate_img`.
3. Insert one raw property record with
   `insert_property_record_before`; derive an anchor that actually exists in
   every target IMG from its scanned order.
4. Replace a complete top-level raw record and update only affected ancestor
   sizes/references.

Use the helpers in
`tool/scripts/migration/migrate_arcane_river_expansion.py`:

- `raw_record_state` captures every record's raw bytes and sibling order.
- `verify_raw_record_scope` verifies bounded replacements/scalar edits.
- `verify_raw_record_insert_scope` verifies bounded insertions.
- `append_property_record` and `insert_property_record_before` insert without
  reserializing existing siblings.
- `append_xml_properties` inserts targeted XML properties without regenerating
  the complete document.
- `atomic_write_bytes` and `atomic_write_text` commit only a validated result.

Do not use `encode_image_body()`, `save_as()`, or another full-tree writer on an
existing IMG. Do not remove a node and append it at the end to simplify an edit.
Property order, string-block representation, offsets, parent sizes, links, and
untouched payload bytes can all matter to the old client.

Full serialization is acceptable only for a genuinely new standalone IMG or a
new temporary artifact. A new record inside an existing IMG is not a new
standalone artifact and still requires raw insertion.

## 3. Move data across regions safely

The TMS tree is typically BMS-keyed while this client is GMS-keyed. Load source
and target independently with the correct keys. Resolve UOL/outlink chains from
the real source; do not guess paths.

When copying Canvas data, use the established `CanvasMaterializer` path. Client
payloads must be GMS ARGB4444 (`format=1`, `format2=0`) unless a working legacy
record proves a different contract. Preserve dimensions, origin, z-order,
delay, frame order, alpha, and parent relationships unless a documented
compatibility projection requires a change.

A valid Canvas header is insufficient. Decode it with
`wzpy.canvas.decode_canvas(..., region="GMS")` and verify expected visible
frames have a non-empty bounding box. Treat intentional `1x1` placeholders
separately from visible frames.

## 4. Keep server XML incremental

Server `.img.xml` files are independent data sources; changing them does not
change the client IMG. Update only approved `<imgdir>` blocks in place. Preserve
sibling order and bytes outside those blocks as far as practical. Do not parse
and rewrite a complete XML document for a small edit.

After each XML change:

- parse with `xml.etree.ElementTree`;
- compare changed IDs and fields to the approved set;
- verify corresponding client/server IDs and values;
- run the generator twice and require stable hashes.

Update `gms-server/wz-zh-CN` as well when that tree is a runtime consumer or the
existing platform writes both trees. Do not add a parallel translation record
without confirming it belongs to the requested contract.

## 5. Packed WZ boundary

The repository's canonical editable client resources are the IMG files under
`clien/Data`. Validate those IMG files directly; ordinary modification and
verification tasks must not create a temporary or production packed WZ. Do not
run `pack_img_wz.sh`, `VerifyPackedImgWz`, or an equivalent pack/reopen workflow
unless the user explicitly requests a packed output in the current task.

Do not directly patch or overwrite a production packed WZ. If the only input is
a WZ, establish its exact version and region, extract it to an isolated
directory with a proven tool, preserve the original, and perform the same
static IMG checks on the extracted records.

Only when packaging is explicitly requested, treat it as a separate deliverable
after all static gates pass. Confirm the version, region, input directory, and
output path before creating it; never substitute a verification package for
the canonical IMG sources.

## 6. Diagnose startup failures first at the raw layout

When the client reports incorrect game data before login:

1. Stop stacking experiments.
2. Compare every modified client IMG to the last working raw-record layout.
3. Check file-size jumps, all-record rewrites, string-block representation,
   sibling reordering, duplicate/alias roots, truncation, and parse warnings.
4. Restore or reconstruct a clean baseline, then apply only approved raw
   records incrementally.
5. Keep String files exact when the task does not require them.

Do not begin by changing bosses, effects, server damage logic, hooks, DLLs, or
unrelated maps without evidence that the startup parser reached those systems.
