# Free Market Fifth Job Goddess: Cygnus Advancement Design

## Goal

Enable the Free Market Fifth Job Goddess NPC (`9900008`) for Cygnus Knights while keeping Adventurers and Aran unavailable. Eligible Cygnus characters complete a server-specific fifth-job process that advances them directly to their corresponding fourth-job ID.

## Scope

Only `gms-server/scripts-zh-CN/npc/9900008.js` changes. The removed fifth-job skill panel is not restored, and the NPC does not grant fifth-job skills.

## Job Routing

- Adventurer jobs and Aran jobs receive: `当前职业还没开放，你就等吧！`
- Cygnus Knight branches enter the advancement flow.
- Cygnus Noblesse cannot be mapped to a branch and receives a prompt to complete the first job advancement first.
- Characters already using a fourth-job Cygnus ID receive a completion prompt and cannot pay again.
- Each Cygnus branch advances to its matching fourth-job ID:
  - Dawn Warrior: `1112`
  - Blaze Wizard: `1212`
  - Wind Archer: `1312`
  - Night Walker: `1412`
  - Thunder Breaker: `1512`

## Advancement Requirements

The character must meet all requirements at confirmation time:

- Level 180 or higher.
- One Hero Coin (`4310060`).
- 100 Core Gemstones (`2435719`).
- 500,000,000 mesos.

The existing Hero Coin crafting rule remains available: one each of `4251200`, `4251201`, and `4251202` produces one Hero Coin.

## Interaction Flow

For a supported Cygnus branch, the NPC menu provides advancement and Hero Coin crafting. The advancement prompt shows the target job and all requirements. If any requirement is missing, the NPC lists every missing requirement and changes nothing.

After the player confirms and all requirements pass a final recheck, the script deducts one Hero Coin, 100 Core Gemstones, and 500,000,000 mesos, then changes the character to the mapped fourth-job ID and reports success.

## Safety

- Resource checks run immediately before deductions.
- No resource is deducted when any requirement fails.
- The script rejects unsupported selections and disposes the conversation.
- A character already at fourth job cannot repeat the transaction.

## Verification

Add a targeted script contract test or equivalent static check covering job-family routing, the five target mappings, all four requirements, deduction amounts, the unsupported-job message, and the absence of any call to the fifth-job skill panel. Review the final diff without running the full server build unless script validation requires it.
