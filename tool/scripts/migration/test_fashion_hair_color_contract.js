const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const scriptPath = path.resolve(
    __dirname,
    "../../../gms-server/scripts-zh-CN/BeiDouSpecial/发色选择.js"
);
const hairBasePath = path.resolve(
    __dirname,
    "../../../gms-server/src/main/resources/hair-base-ids.txt"
);
const clientHairPath = path.resolve(__dirname, "../../../clien/Data/Character/Hair");
const scriptSource = fs.readFileSync(scriptPath, "utf8");

function runHairColorStart({ hair, isRetainedHair, itemExists }) {
    const events = {
        disposed: false,
        messages: [],
        previews: [],
    };
    const player = {
        getHair: () => hair,
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
