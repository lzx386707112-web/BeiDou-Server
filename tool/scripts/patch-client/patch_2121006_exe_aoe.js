#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "../../..");
const exePath = path.join(root, "clien", "BeiDou.exe");
const backupPath = `${exePath}.bak-2121006-exe-aoe`;

const imageBase = 0x400000;
const hookVa = 0x955d0e;
const hookOffset = hookVa - imageBase;
const caveVa = 0xaef602;
const caveOffset = caveVa - imageBase;
const aoeVa = 0x956372;
const returnVa = 0x955d19;

const originalHook = "3dad9521000f8459060000";

function rel32(fromVa, toVa) {
  const value = (toVa - (fromVa + 5)) | 0;
  const out = Buffer.alloc(4);
  out.writeInt32LE(value, 0);
  return out;
}

function jmp(fromVa, toVa) {
  return Buffer.concat([Buffer.from([0xe9]), rel32(fromVa, toVa)]);
}

function je(fromVa, toVa) {
  const out = Buffer.alloc(6);
  out[0] = 0x0f;
  out[1] = 0x84;
  out.writeInt32LE((toVa - (fromVa + 6)) | 0, 2);
  return out;
}

function cmpEaxImm32(value) {
  const out = Buffer.alloc(5);
  out[0] = 0x3d;
  out.writeUInt32LE(value >>> 0, 1);
  return out;
}

function buildCave() {
  const chunks = [];
  let va = caveVa;

  chunks.push(cmpEaxImm32(2121006));
  va += 5;
  chunks.push(je(va, aoeVa));
  va += 6;

  chunks.push(cmpEaxImm32(2201005));
  va += 5;
  chunks.push(je(va, aoeVa));
  va += 6;

  chunks.push(jmp(va, returnVa));
  return Buffer.concat(chunks);
}

function hexAt(buffer, offset, length) {
  return buffer.subarray(offset, offset + length).toString("hex");
}

function main() {
  const dryRun = process.argv.includes("--dry-run");
  if (!fs.existsSync(exePath)) {
    throw new Error(`BeiDou.exe not found: ${exePath}`);
  }

  const buffer = fs.readFileSync(exePath);
  const hookPatch = Buffer.concat([jmp(hookVa, caveVa), Buffer.alloc(6, 0x90)]);
  const cavePatch = buildCave();
  const currentHook = hexAt(buffer, hookOffset, originalHook.length / 2);
  const currentCave = hexAt(buffer, caveOffset, cavePatch.length);

  const alreadyPatched =
    currentHook === hookPatch.toString("hex") &&
    currentCave === cavePatch.toString("hex");

  if (alreadyPatched) {
    console.log("BeiDou.exe already has the 2121006 AoE hook.");
    return;
  }

  if (currentHook !== originalHook) {
    throw new Error(
      `Unexpected hook bytes at 0x${hookOffset.toString(16)}: ${currentHook}; ` +
        `expected ${originalHook}`
    );
  }

  if (!/^0+$/.test(currentCave)) {
    throw new Error(
      `Code cave is not empty at 0x${caveOffset.toString(16)}: ${currentCave}`
    );
  }

  console.log(
    `2121006 AoE hook: VA 0x${hookVa.toString(16)} -> cave VA 0x${caveVa.toString(16)}`
  );
  console.log(`Cave bytes (${cavePatch.length}): ${cavePatch.toString("hex")}`);

  if (dryRun) {
    console.log("[dry-run] no files written");
    return;
  }

  if (!fs.existsSync(backupPath)) {
    fs.copyFileSync(exePath, backupPath);
    console.log(`Backup created: ${backupPath}`);
  }

  hookPatch.copy(buffer, hookOffset);
  cavePatch.copy(buffer, caveOffset);
  fs.writeFileSync(exePath, buffer);
  console.log("BeiDou.exe 2121006 AoE hook applied.");
}

main();
