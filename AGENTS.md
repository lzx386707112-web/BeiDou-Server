@/Users/lizixian/.codex/RTK.md

# BeiDou-Server Project Instructions

These instructions apply to the entire repository. They are mandatory for
client WZ/IMG work, skill migrations, compatibility DLL changes, server logic,
builds, tests, and delivery copies.

## Project WZ/IMG Skill

For every task that diagnoses, reads, changes, migrates, packs, verifies, or
delivers client WZ/IMG resources or their matching server XML, first read and
follow `.codex/skills/beidou-wz-img/SKILL.md` and every reference it marks as
required for the affected resource type. This includes Quest, Skill, Map, NPC,
Mob, Item, String, Effect, and Resource Workbench operations.

## Core Rule

This is a compatibility migration project, not a clean-room rewrite and not a
one-to-one copy of modern TMS data. Preserve the old client's proven binary and
runtime contracts. Make the smallest evidence-backed change that produces the
requested effect.

Never treat "the file parses in our tools" as proof that the old client will
accept it. Startup compatibility, binary stability, playback behavior, server
timing, and delivery integrity are separate verification gates.

## Known Startup Failure Pattern

The Bishop migration incident established a concrete failure signature:

- A full `encode_image_body()` round trip changed all 34 skill records in
  `232.img`, although only a small subset of skills needed edits.
- The writer converted existing property names to inline string blocks and
  increased the IMG by several MiB without producing parser warnings.
- Removing and reappending `String/Skill.img` nodes changed their order even
  when most string values were semantically unchanged.
- Repository parsers and semantic contract tests accepted these files, but the
  old client rejected them during startup with "incorrect game data".
- Restoring `String/Skill.img` exactly and changing only nine raw `232.img`
  skill records removed the startup failure.

When that startup message appears before login, first compare modified client
IMG files against the last working raw-record layout. Do not start by changing
effects, server damage logic, DLL hooks, or unrelated resources.

## Start Every Task With Evidence

Before editing:

1. Read `git status --short` and preserve all existing user changes.
2. Read the relevant migration notes, generator, contract tests, logs, and the
   newest user video or runtime log.
3. Identify the last known working artifact and extract a clean baseline when
   one is needed.
4. State the suspected cause, allowed change set, success criteria, and the
   checks that will prove the change safe.
5. Distinguish startup failures from runtime visual, targeting, timing, and
   server damage failures. Do not assume one fix covers all of them.

Do not stack another experiment on top of an unverified or partially reverted
artifact. Complete the rollback or baseline reconstruction first.

## Preserve The Worktree

- Existing modified and untracked files belong to the user unless the current
  task clearly created them.
- Do not use `git reset --hard`, `git checkout --`, broad restores, or bulk
  cleanup commands.
- Do not reformat, reorder, or refactor unrelated code or XML.
- Apply manual source edits with `apply_patch` and keep diffs surgical.
- Generated binary replacement is allowed only through a reviewed generator or
  an exact baseline copy followed by an incremental patch.
- Remove only temporary files created by the current task, using exact paths.

## WZ And IMG Binary Safety

Existing client IMG files are binary compatibility artifacts. Their property
order, string-block representation, record boundaries, parent block sizes,
links, and untouched payload bytes can matter to the old client.

### Forbidden By Default

- Do not run `encode_image_body()`, `save_as()`, or another full-tree writer on
  an existing client IMG merely to change a few nodes.
- Do not parse an existing IMG and serialize the entire property tree back.
- Do not delete and reappend existing properties when an in-place or
  record-level replacement is possible; this changes order.
- Do not rewrite the complete client `String/Skill.img` for a name, description,
  or level-text edit.
- Do not rewrite a complete server XML file when only specific `<imgdir>`
  blocks need to change.
- Do not assume semantic equality is binary compatibility.
- Do not use `rtk git show > binary-file`; RTK filtering can corrupt binary
  stdout.

### Required Technique

Prefer, in this order:

1. Same-length in-place scalar or string-payload patch.
2. Raw property-record replacement inside the existing parent block.
3. Raw top-level IMG record replacement with the parent block length updated.
4. Full serialization only when creating a new standalone artifact or when the
   user explicitly approves a proven whole-file migration.

When a Git baseline is required, extract binary data through raw Git plumbing,
for example:

```bash
rtk proxy sh -c 'git cat-file blob HEAD:clien/Data/Skill/232.img > /tmp/baseline-232.img'
```

For every incremental IMG patch:

- Record the exact property or skill IDs allowed to change.
- Capture raw record spans and hashes before editing.
- Preserve every unmodified record byte-for-byte.
- Preserve top-level property order and skill-node order.
- Update only the affected parent block-size field.
- Parse the result independently and reject `truncated` or any
  `parse_warnings`.
- Run the generator twice and require identical hashes after the first run.

If an existing full writer is the only available implementation, stop and add
an incremental path before modifying the production IMG.

## Client Resource Compatibility

- All migrated skill Canvas payloads must remain GMS-keyed ARGB4444:
  `format=1`, `format2=0`.
- Preserve source frame delays, origins, z-order, dimensions, animation order,
  UOL/outlink semantics, and parent relationships unless evidence requires a
  documented compatibility projection.
- Resolve and verify the actual TMS/MS resource reference chain. Do not guess
  resource paths, property names, coordinate systems, or parent layers.
- Modern nodes must be projected onto structures already proven to work in the
  old client. Do not copy unsupported modern schemas wholesale.
- For summons, compare with a working legacy summon and verify required
  `summon/attack1/info` fields such as `range`, `type`, `attackAfter`, and
  `mobCount`.
- A `1x1` Canvas may be an intentional placeholder; distinguish it from a
  visible frame before declaring an effect complete.
- A valid Canvas header is not enough. Decode the payload and check that the
  expected frames contain visible pixels.

## Runtime Hooks And Playback Evidence

Do not guess hooks, addresses, calling threads, object types, or D3D timing.
Before adding or moving a client hook, establish from disassembly and logs:

- the local-player execution path;
- the true visual-node creation entry;
- the calling thread and safe call phase;
- coordinate space and map/screen transforms;
- resource path and parent layer;
- node ownership, lifetime, and destruction path;
- whether replay/remote-character paths are actually relevant.

Do not repeat a previously failed hook or direct visual-layer creation approach
without new evidence that invalidates the earlier result. Keep probes versioned
and remove obsolete experimental hooks and capture state during rollback.

## Skill Contract Checklist

For every added, modified, or removed skill, audit the full contract:

- client `clien/Data/Skill/<book>.img`;
- client `clien/Data/String/Skill.img` only when truly necessary;
- client MCV/Map Effect resources when used;
- compatibility DLL routing and skill classification;
- server `gms-server/wz/Skill.wz/<book>.img.xml`;
- server String XML only when truly necessary;
- Java skill constants, handlers, schedules, summons, statuses, and cleanup;
- skill grant/removal scripts, active-skill arrays, master levels, and keymaps;
- hidden replay-stage IDs and their visibility/grant behavior.

Verify action name, damage, hit count, target count, range, MP cost, cooldown,
duration, element, summon movement type, attack interval, hit timing, and hit
effect. Damage must not be applied before the corresponding visual impact unless
the source behavior and old-client limitation are explicitly documented.

Deleting a passive or active skill requires removing all grant, keymap, client,
server, runtime, and documentation references without shifting unrelated IDs.

## XML Safety

- Replace only the intended `<imgdir>` blocks in place.
- Preserve sibling order and all bytes outside the approved blocks as far as
  practical.
- Do not remove nodes and append them at the end merely for convenience.
- Parse the resulting XML and compare semantic changes against the approved ID
  set.
- Run XML generators twice and require stable hashes.

## Verification Gates

Before delivery, perform checks proportional to the changed surface. Client
skill-resource work must include all of the following:

1. Syntax/static checks for modified scripts and source.
2. Targeted contract tests for the affected profession and skill-grant flow.
3. Raw-record comparison proving that only approved IMG records changed.
4. Exact comparison for files intended to remain at baseline, especially
   `String/Skill.img`.
5. Full IMG parse with no truncation or warnings.
6. Canvas format audit and payload decoding for every affected skill Canvas.
7. Validate modified client IMG files directly with static raw-record, parse,
   path/value, and Canvas decode checks. Do not create a temporary packed WZ for
   ordinary verification unless the user explicitly requests packaging.
8. Generator idempotence: run twice and compare SHA-256 hashes.
9. Relevant MCV header, frame-count, duration, alpha, and visible-tail checks.
10. Run targeted static/source checks when DLL source or routing is involved;
    rebuild the DLL only when the user explicitly requests it.
11. Run targeted static/source checks when server code is involved; rebuild the
    server JAR only when the user explicitly requests it.
12. Run `git diff --check` and inspect the final diff and change set.

Run the broader contract suite when feasible. If it fails because earlier user
work intentionally removed skills or changed expectations, report the exact
unrelated failures. Do not restore deleted features or weaken tests merely to
make the suite green.

Offline tools cannot prove Windows/Winlator runtime behavior. After all offline
gates pass, explicitly list the remaining startup and in-game verification
points: launch, login, cast animation, target collection, damage timing, hit
effect, movement, other-player view, map transition, and repeated casting.

## Delivery Rules

- Never sync an unverified artifact to `/Users/lizixian/Downloads`.
- Run the required static validation locally first. Build or package only when
  the user explicitly requests it.
- Preserve every delivery filename and requested directory layout.
- Do not rename files, add version suffixes, or include temporary baselines,
  backups, probe builds, or verification WZ packages.
- Copy only the runtime files required for the requested change.
- Compare source and delivery SHA-256 hashes for every copied file.
- Report the exact delivery directory and any verification that still requires
  the user's runtime environment.

## Definition Of Done

A task is not complete because code was edited or a file parsed. It is complete
only when:

- the root cause is supported by logs, binary comparison, disassembly, source
  data, or a working legacy analogue;
- the change set is minimal and explicitly bounded;
- untouched binary records are proven unchanged;
- relevant client, server, DLL, scripts, and grant paths agree;
- required static validation gates and any explicitly requested builds pass;
- the generator is idempotent;
- verified delivery files are synchronized with matching hashes; and
- remaining real-client risks are stated plainly.
