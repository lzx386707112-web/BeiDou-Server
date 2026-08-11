#!/usr/bin/env node

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../../..");
const menuPath = path.join(root, "gms-server/scripts-zh-CN/npc/9900009.js");
const scriptPath = path.join(root, "gms-server/scripts-zh-CN/npc/坐骑领取.js");
const menuSource = fs.readFileSync(menuPath, "utf8");
const source = fs.readFileSync(scriptPath, "utf8");
const inventoryType = { EQUIP: "EQUIP" };

function loadScript(options = {}) {
    const events = { disposed: false, gained: [], messages: [], openedNpcs: [], skills: [] };
    const owned = new Set(options.owned || []);
    const inventory = { getNumFreeSlot: () => options.freeSlots === undefined ? 10 : options.freeSlots };
    const player = {
        getInventory: (type) => {
            assert.equal(type, inventoryType.EQUIP);
            return inventory;
        },
        getItemQuantity: (itemId, checkEquipped) => {
            assert.equal(checkEquipped, true);
            return owned.has(itemId) ? 1 : 0;
        },
    };
    const context = {
        Java: {
            type(name) {
                assert.equal(name, "org.gms.client.inventory.InventoryType");
                return inventoryType;
            },
        },
        cm: {
            dispose: () => { events.disposed = true; },
            gainItem: (itemId, quantity) => events.gained.push([itemId, quantity]),
            getJobId: () => options.jobId === undefined ? 100 : options.jobId,
            getPlayer: () => player,
            openNpc: (npcId) => events.openedNpcs.push(npcId),
            sendOk: (message) => events.messages.push(message),
            sendSimple: (message) => events.messages.push(message),
            sendYesNo: (message) => events.messages.push(message),
            teachSkill: (skillId, level, masterLevel, expiration) => {
                events.skills.push([skillId, level, masterLevel, expiration]);
            },
        },
    };
    vm.createContext(context);
    vm.runInContext(source, context, { filename: scriptPath });
    return { context, events };
}

const expectedPairs = [
    [1902000, 1912000], [1902001, 1912000], [1902002, 1912000], [1902004, 1912002],
    [1902005, 1912005], [1902006, 1912005], [1902007, 1912005], [1902008, 1912003],
    [1902009, 1912004], [1902010, 1912006], [1902011, 1912007], [1902012, 1912008],
    [1902013, 1912009], [1902014, 1912010], [1902015, 1912011], [1902016, 1912011],
    [1902017, 1912011], [1902018, 1912011], [1902019, 1912012], [1902020, 1912013],
    [1902021, 1912014], [1902022, 1912015], [1902023, 1912016], [1902028, 1912021],
    [1902031, 1912024], [1902033, 1912026], [1902034, 1912027], [1902036, 1912029],
    [1902037, 1912030], [1902038, 1912031], [1902039, 1912032], [1902045, 1912038],
    [1902047, 1912040], [1902048, 1912041], [1902059, 1912052], [1902060, 1912053],
    [1902401, 1912401], [1902403, 1912403],
];

assert(menuSource.includes('#L4##b坐骑领取#k#l'), "Trend Front menu is missing the mount entry");
assert(menuSource.includes('cm.openNpc(9900009, "坐骑领取")'), "mount entry does not open the claim script");

{
    const { context, events } = loadScript();
    assert.deepEqual(Array.from(context.mountPairs, (pair) => Array.from(pair)), expectedPairs);
    assert.equal(new Set(expectedPairs.map((pair) => pair[0])).size, expectedPairs.length);
    context.start();
    assert.match(events.messages[0], /第 1\/4 页/);
    assert.match(events.messages[0], /#z1902000#/);
    context.action(1, 0, context.NEXT_PAGE);
    assert.equal(context.currentPage, 1);
    assert.match(events.messages[1], /#z1902011#/);
    context.action(1, 0, context.BACK_TO_TREND_FRONT);
    assert.deepEqual(events.openedNpcs, [9900009]);
}

for (const [mountId, saddleId] of expectedPairs) {
    for (const itemId of [mountId, saddleId]) {
        const filename = String(itemId).padStart(8, "0");
        assert(fs.existsSync(path.join(root, `clien/Data/Character/TamingMob/${filename}.img`)),
            `missing client TamingMob item ${itemId}`);
        assert(fs.existsSync(path.join(root, `gms-server/wz/Character.wz/TamingMob/${filename}.img.xml`)),
            `missing server TamingMob item ${itemId}`);
    }
    const saddleSource = fs.readFileSync(path.join(root,
        `gms-server/wz/Character.wz/TamingMob/${String(saddleId).padStart(8, "0")}.img.xml`), "utf8");
    assert(saddleSource.includes(`<imgdir name="${mountId}">`),
        `saddle ${saddleId} is not linked to mount ${mountId}`);
}

{
    const { context, events } = loadScript({ jobId: 100, freeSlots: 2 });
    context.selectedMountIndex = 0;
    context.claimMount();
    assert.deepEqual(events.gained, [[1902000, 1], [1912000, 1]]);
    assert.deepEqual(events.skills, [[1004, 1, 1, -1]]);
}

{
    const { context, events } = loadScript({ jobId: 1100, freeSlots: 2 });
    context.selectedMountIndex = 4;
    context.claimMount();
    assert.deepEqual(events.gained, [[1902005, 1], [1912005, 1]]);
    assert.deepEqual(events.skills, [[10001004, 1, 1, -1]]);
}

{
    const { context, events } = loadScript({ jobId: 2112, freeSlots: 1, owned: [1912002] });
    context.selectedMountIndex = 3;
    context.claimMount();
    assert.deepEqual(events.gained, [[1902004, 1]]);
    assert.deepEqual(events.skills, [[20001004, 1, 1, -1]]);
}

{
    const { context, events } = loadScript({ jobId: 100, freeSlots: 1 });
    context.selectedMountIndex = 0;
    context.claimMount();
    assert.deepEqual(events.gained, []);
    assert.deepEqual(events.skills, []);
    assert.match(events.messages[0], /装备栏空间不足/);
}

{
    const { context, events } = loadScript({ jobId: 1100, freeSlots: 2 });
    context.selectedMountIndex = 0;
    context.claimMount();
    assert.deepEqual(events.gained, []);
    assert.deepEqual(events.skills, []);
}

{
    const { context, events } = loadScript({ jobId: 2200, freeSlots: 2 });
    context.selectedMountIndex = 3;
    context.claimMount();
    assert.deepEqual(events.gained, []);
    assert.deepEqual(events.skills, []);
}

console.log("mount claim contract: 38 mount and saddle pairs ok");
