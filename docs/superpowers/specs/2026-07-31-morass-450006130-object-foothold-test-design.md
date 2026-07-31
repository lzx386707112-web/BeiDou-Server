# Morass 450006130 Object Foothold Compatibility Test

## Objective

Determine whether the legacy client high-load black screen on map `450006130`
is caused by the `foothold` metadata embedded in the referenced
`morass.img/castle_Outside/foothold_Bridge` Canvas nodes.

## Evidence

- A map with no Morass objects loads without abnormal CPU usage.
- A single `foothold_Bridge/l2=0` object still triggers the issue.
- Independent `l2=0`, `l2=1`, and `l2=2/4` groups all trigger the issue.
- The four Canvas resources decode correctly and use the legacy ARGB4444 format.
- Their common relevant metadata is the Canvas `foothold` child.
- Each tested object foothold segment already has an exact fixed counterpart in
  the map's top-level `foothold` tree.

## Selected Test

Keep the current eighth-round B map unchanged. It contains six `connect`
objects and six Morass objects: four `foothold_Bridge/l2=2` instances and two
`foothold_Bridge/l2=4` instances.

Create a test copy of `clien/Data/Map/Obj/morass.img` and remove only these two
nodes:

- `castle_Outside/foothold_Bridge/2/0/foothold`
- `castle_Outside/foothold_Bridge/4/0/foothold`

Do not change Canvas pixels, dimensions, format, origin, z-order, map objects,
the map's fixed foothold tree, NPCs, life, backgrounds, miniMap, BGM, portals,
or the server map XML.

## Alternatives Rejected

- Replacing the Canvas images would change both pixel data and metadata, so a
  successful result would not identify the responsible variable.
- Deleting the objects is already known to avoid the issue but removes visible
  map content and does not identify why the old client rejects the objects.

## Packaging And Installation

- Generate `下载/神秘河/AB测试_450006130_第十一轮` with the unchanged current
  map IMG, unchanged server XML, sanitized `morass.img`, original `morass.img`,
  a README, and SHA256 hashes.
- Back up the current project map IMG, server XML, and original `morass.img` to
  a timestamped directory under `/private/tmp` before installation.
- Install only the sanitized `morass.img`; keep the current eighth-round B map
  IMG and server XML byte-identical.

## Verification

- The sanitized resource must parse and re-encode successfully.
- All Canvas payload hashes and all resource nodes except the two removed
  `foothold` children must match the original resource.
- The installed map IMG and server XML must retain their eighth-round B hashes.
- The installed `morass.img` must match the generated sanitized resource.
- The backup must retain the original `morass.img` hash.

## Result Interpretation

- If the map loads normally, object Canvas foothold metadata is the confirmed
  compatibility trigger. The production fix can remove equivalent redundant
  metadata only where fixed map footholds exist.
- If high load remains, restore the original resource and test the Canvas
  payload independently with a known-compatible placeholder; do not delete
  additional map nodes in the same test.
