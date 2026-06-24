#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "../..");
const exePath = path.join(root, "clien", "BeiDou.exe");
const backupPath = `${exePath}.bak-bigbang-aoe`;

const patches = [
  {
    name: "Big Bang horizontal charge divisor",
    offset: 0x55640b,
    before: "b9c8000000",
    after: "b932000000",
  },
  {
    name: "Big Bang horizontal base range",
    offset: 0x556412,
    before: "6ab5",
    after: "6a80",
  },
  {
    name: "Big Bang vertical base range",
    offset: 0x556428,
    before: "6a9c",
    after: "6a80",
  },
];

function hexAt(buffer, offset, length) {
  return buffer.subarray(offset, offset + length).toString("hex");
}

function main() {
  if (!fs.existsSync(exePath)) {
    throw new Error(`BeiDou.exe not found: ${exePath}`);
  }

  const buffer = fs.readFileSync(exePath);
  let alreadyPatched = true;
  let needsPatch = false;

  for (const patch of patches) {
    const before = Buffer.from(patch.before, "hex");
    const after = Buffer.from(patch.after, "hex");
    const current = hexAt(buffer, patch.offset, before.length);

    if (current === patch.before) {
      alreadyPatched = false;
      needsPatch = true;
      continue;
    }
    if (current === patch.after) {
      continue;
    }

    throw new Error(
      `${patch.name} unexpected bytes at 0x${patch.offset.toString(16)}: ` +
        `${current}; expected ${patch.before} or ${patch.after}`
    );
  }

  if (alreadyPatched) {
    console.log("BeiDou.exe already has the Big Bang AoE patch.");
    return;
  }

  if (needsPatch && !fs.existsSync(backupPath)) {
    fs.copyFileSync(exePath, backupPath);
    console.log(`Backup created: ${backupPath}`);
  }

  for (const patch of patches) {
    const before = Buffer.from(patch.before, "hex");
    const after = Buffer.from(patch.after, "hex");
    const current = hexAt(buffer, patch.offset, before.length);

    if (current === patch.before) {
      after.copy(buffer, patch.offset);
      console.log(`Patched ${patch.name} at 0x${patch.offset.toString(16)}`);
    }
  }

  fs.writeFileSync(exePath, buffer);
  console.log("BeiDou.exe Big Bang AoE patch applied.");
}

main();
