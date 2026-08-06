const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const scriptPath = path.resolve(
    __dirname,
    "../../../gms-server/scripts-zh-CN/BeiDouSpecial/发色选择.js"
);
const hairstyleScriptPath = path.resolve(
    __dirname,
    "../../../gms-server/scripts-zh-CN/BeiDouSpecial/皇家发型.js"
);
const hairBasePath = path.resolve(
    __dirname,
    "../../../gms-server/src/main/resources/hair-base-ids.txt"
);
const clientHairPath = path.resolve(__dirname, "../../../clien/Data/Character/Hair");
const scriptSource = fs.readFileSync(scriptPath, "utf8");
const hairstyleScriptSource = fs.readFileSync(hairstyleScriptPath, "utf8");

function runHairColorStart({ hair, isRetainedHair, itemExists, isGM = false }) {
    const events = {
        disposed: false,
        messages: [],
        previews: [],
    };
    const player = {
        getHair: () => hair,
        isGM: () => isGM,
    };
    const context = {
        Java: {
            type(name) {
                assert.equal(name, "org.gms.constants.inventory.ItemConstants");
                return { isNewHair: isRetainedHair };
            },
        },
        cm: {
            dispose() {
                events.disposed = true;
            },
            getPlayer: () => player,
            isCosmeticEquipped: (hairId) => hairId === hair,
            itemExists,
            sendOk(message) {
                events.messages.push(message);
            },
            sendStyle(message, styles) {
                events.previews.push({ message, styles: Array.from(styles) });
            },
        },
    };

    vm.runInNewContext(scriptSource, context, { filename: scriptPath });
    context.start();
    return events;
}

function runHairColorChange({ isGM, cash }) {
    const events = { cashChanges: [], hairChanges: [], messages: [] };
    const cashShop = {
        gainCash: (type, amount) => events.cashChanges.push({ type, amount }),
        getCash: () => cash,
    };
    const context = {
        Java: { type: () => ({ isNewHair: () => true }) },
        cm: {
            dispose() {},
            getPlayer: () => ({ getCashShop: () => cashShop, isGM: () => isGM }),
            sendOk: (message) => events.messages.push(message),
            setHair: (hairId) => events.hairChanges.push(hairId),
        },
    };
    vm.runInNewContext(scriptSource, context, { filename: scriptPath });
    context.newHairs = [40071];
    context.设置发色(0);
    return events;
}

function runHairstyleChange({ isGM, itemId, random }) {
    const events = { consumedItems: [], hairChanges: [], messages: [] };
    const player = { getHair: () => 40070, isGM: () => isGM };
    const context = {
        Java: { type: () => ({ getInstance: () => ({ getName: () => "test hair" }) }) },
        cm: {
            dispose() {},
            gainItem: (id, amount) => events.consumedItems.push({ id, amount }),
            getCosmeticItem: (id) => id,
            getPlayer: () => player,
            haveItem: (id) => id === itemId,
            isCosmeticEquipped: () => false,
            sendOk: (message) => events.messages.push(message),
            setHair: (hairId) => events.hairChanges.push(hairId),
        },
    };
    vm.runInNewContext(hairstyleScriptSource, context, { filename: hairstyleScriptPath });
    if (random) {
        context.status = 1;
        context.beauty = 1;
        context.action(1, 0, 0);
    } else {
        context.applySelectedHair(40071);
    }
    return events;
}

{
    const events = runHairColorStart({
        hair: 39990,
        isRetainedHair: () => false,
        itemExists: () => true,
    });

    assert.equal(events.previews.length, 0, "unavailable hair must not send a style preview");
    assert.equal(events.messages.length, 1, "unavailable hair must show a message");
    assert.equal(events.disposed, true, "unavailable hair must end the conversation");
}

{
    const events = runHairColorChange({ isGM: true, cash: 0 });
    assert.deepEqual(events.hairChanges, [40071], "GM must change hair color without cash");
    assert.deepEqual(events.cashChanges, [], "GM hair color change must not consume cash");
}

{
    const events = runHairColorChange({ isGM: false, cash: 0 });
    assert.deepEqual(events.hairChanges, [], "a regular player without cash must be rejected");
    assert.deepEqual(events.cashChanges, []);
}

{
    const events = runHairColorChange({ isGM: false, cash: 6000 });
    assert.deepEqual(events.hairChanges, [40071], "a funded regular player must still change hair color");
    assert.deepEqual(events.cashChanges, [{ type: 1, amount: -6000 }]);
}

for (const random of [false, true]) {
    const events = runHairstyleChange({ isGM: true, itemId: 0, random });
    assert.equal(events.hairChanges.length, 1, "GM must change hairstyle without a coupon");
    assert.deepEqual(events.consumedItems, [], "GM hairstyle change must not consume a coupon");
}

{
    const events = runHairstyleChange({ isGM: false, itemId: 5150044, random: false });
    assert.deepEqual(events.hairChanges, [40071], "a regular player with a coupon must still change hairstyle");
    assert.deepEqual(events.consumedItems, [{ id: 5150044, amount: -1 }]);
}

{
    const events = runHairstyleChange({ isGM: false, itemId: 5150040, random: true });
    assert.equal(events.hairChanges.length, 1, "a regular player with a coupon must still get a random hairstyle");
    assert.deepEqual(events.consumedItems, [{ id: 5150040, amount: -1 }]);
}

{
    const events = runHairColorStart({
        hair: 40070,
        isRetainedHair: (hairId) => Math.floor(hairId / 10) * 10 === 40070 && hairId % 10 <= 7,
        itemExists: () => true,
    });

    assert.deepEqual(
        events.previews[0].styles,
        [40071, 40072, 40073, 40074, 40075, 40076, 40077],
        "retained hair must preview the other valid colors"
    );
    assert.equal(events.messages.length, 0);
}

{
    const events = runHairColorStart({
        hair: 40070,
        isRetainedHair: (hairId) => Math.floor(hairId / 10) * 10 === 40070 && hairId % 10 <= 7,
        itemExists: (hairId) => hairId === 40070,
    });

    assert.equal(events.previews.length, 0, "an empty color list must not send a style preview");
    assert.equal(events.messages.length, 1, "an empty color list must show a message");
    assert.equal(events.disposed, true, "an empty color list must end the conversation");
}

{
    const retainedBases = fs.readFileSync(hairBasePath, "utf8")
        .trim()
        .split(/\s+/)
        .map(Number)
        .sort((left, right) => left - right);
    const clientBases = Array.from(new Set(
        fs.readdirSync(clientHairPath)
            .filter((name) => /^\d{8}\.img$/.test(name))
            .map((name) => Math.floor(Number.parseInt(name, 10) / 10) * 10)
    )).sort((left, right) => left - right);

    assert.deepEqual(
        retainedBases,
        clientBases,
        "the retained-hair whitelist must match the client Hair resources"
    );
}

console.log("fashion hair color contract: ok");
