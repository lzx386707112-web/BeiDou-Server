#!/usr/bin/env node

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "../../..");
const scriptPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/装备制作/套装进化.js");
const progressPath = path.join(root, "gms-server/src/main/java/org/gms/server/EquipmentEvolutionProgress.java");
const monsterPath = path.join(root, "gms-server/src/main/java/org/gms/server/life/Monster.java");
const dropPath = path.join(root,
    "gms-server/src/main/resources/db/migration/V2.1.67__add_reworked_equipment_evolution_drops.sql");

const inventoryType = {EQUIP: "EQUIP"};
const removedEquipment = [];
const itemProvider = {getEquipById: (itemId) => ({itemId})};
const job = {getJobStyleInternal: () => ({getJobNiche: () => 1})};
const quest = {getInstance: (questId) => ({getName: () => `quest-${questId}`})};
const javaTypes = {
    "org.gms.client.inventory.InventoryType": inventoryType,
    "org.gms.client.inventory.manipulator.InventoryManipulator": {
        removeFromSlot: (_client, _type, position) => removedEquipment.push(position),
    },
    "org.gms.server.ItemInformationProvider": {getInstance: () => itemProvider},
    "org.gms.client.Job": job,
    "org.gms.server.quest.Quest": quest,
};
const context = {
    Java: {type: (name) => javaTypes[name] || {}},
    Math: Object.create(Math),
};
vm.createContext(context);
const source = fs.readFileSync(scriptPath, "utf8");
vm.runInContext(source, context, {filename: scriptPath});

const stages = Array.from(context.ARMOR_STAGES);
assert.strictEqual(stages.length, 10, "equipment evolution must have ten stages");
assert.deepStrictEqual(stages.map((stage) => stage.level), [30, 45, 70, 80, 100, 120, 140, 160, 200, 200]);
assert.deepStrictEqual(stages.map((stage) => stage.conditions.meso),
    [10000000, 15000000, 50000000, 70000000, 100000000,
        200000000, 400000000, 500000000, 800000000, 800000000]);
assert.deepStrictEqual(stages.map((stage) => stage.conditions.cash),
    [1000, 2000, 3000, 3500, 5000, 6000, 7000, 7500, 8000, 8000]);
assert.strictEqual(context.STAGE_KEY_PREFIX, "equip_upgrade_v2_stage_");
assert.strictEqual(context.KILL_KEY_PREFIX, "equip_upgrade_v2_kill_");
assert.strictEqual(context.UPGRADE_SUCCESS_RATE, 80);

for (const [stageIndex, stage] of stages.entries()) {
    const itemIds = Array.from(stage.conditions.items, (entry) => entry[0]);
    assert.strictEqual(new Set(itemIds).size, itemIds.length, `stage ${stageIndex} has duplicate material ids`);
    const killIds = Array.from(stage.conditions.killMobs, (entry) => entry[0]);
    assert.strictEqual(new Set(killIds).size, killIds.length, `stage ${stageIndex} has duplicate mob ids`);
}
assert(stages[5].conditions.items.some((entry) => entry[0] === 4000176 && entry[1] === 10));
assert(stages[5].conditions.items.some((entry) => entry[0] === 4000240 && entry[1] === 100));
assert(stages[8].conditions.items.some((entry) => entry[0] === 4251201 && entry[1] === 2));

const expectedStage8Sacrifices = [
    [1005196, 1052804, 1042254, 1072967, 1082593],
    [1005197, 1052805, 1042255, 1072968, 1082594],
    [1005198, 1052806, 1042256, 1072969, 1082595],
    [1005199, 1052807, 1042257, 1072970, 1082596],
    [1005200, 1052808, 1042258, 1072971, 1082597],
];
for (let jobIndex = 0; jobIndex < 5; jobIndex++) {
    assert.deepStrictEqual(
        Array.from(context.getEquipSacrifices(stages[8].conditions, jobIndex), (entry) => entry.itemId),
        expectedStage8Sacrifices[jobIndex]
    );
}

function makeConversation(stageIndex, random, counts = {}) {
    const values = new Map([[`${context.STAGE_KEY_PREFIX}armor`, String(stageIndex)]]);
    for (const [key, value] of Object.entries(counts)) values.set(key, String(value));
    const gains = [];
    const equips = [];
    const messages = [];
    let mesoDelta = 0;
    let cashDelta = 0;
    const inventory = {
        findById: (itemId) => ({getPosition: () => itemId % 1000}),
        getNumFreeSlot: () => 10,
    };
    const cm = {
        getCharacterExtendValue: (key) => values.get(key) || null,
        saveOrUpdateCharacterExtendValue: (key, value) => values.set(key, String(value)),
        getPlayer: () => ({
            getLevel: () => 250,
            getJob: () => ({getId: () => 100}),
            getInventory: () => inventory,
            getClient: () => ({}),
            getCashShop: () => ({
                getCash: () => 100000,
                gainCash: (_type, delta) => { cashDelta += delta; },
            }),
        }),
        isQuestCompleted: () => true,
        getItemQuantity: () => 100000,
        getMeso: () => 2000000000,
        gainItem: (itemId, quantity) => gains.push([itemId, quantity]),
        gainMeso: (delta) => { mesoDelta += delta; },
        gainEquip: (equip) => equips.push(equip.itemId),
        sendOk: (message) => messages.push(message),
        dispose: () => {},
    };
    return {
        cm, values, gains, equips, messages,
        getMesoDelta: () => mesoDelta,
        getCashDelta: () => cashDelta,
        random,
    };
}

function satisfyKills(testState, targetStage) {
    for (const [mobId, required] of stages[targetStage].conditions.killMobs) {
        testState.values.set(`${context.KILL_KEY_PREFIX}${targetStage}_${mobId}`, String(required));
    }
}

const success = makeConversation(-1, 0);
satisfyKills(success, 0);
context.cm = success.cm;
vm.runInContext("UPGRADE_SUCCESS_RATE = 101;", context);
removedEquipment.length = 0;
context.doArmorUpgrade();
assert.strictEqual(success.values.get(`${context.STAGE_KEY_PREFIX}armor`), "0", success.messages.join(" | "));
assert.deepStrictEqual(success.equips, [1003922, 1052638, 1072844, 1082536]);
assert.strictEqual(success.getMesoDelta(), -10000000);
assert.strictEqual(success.getCashDelta(), -1000);
for (const [mobId] of stages[0].conditions.killMobs) {
    assert.strictEqual(success.values.get(`${context.KILL_KEY_PREFIX}0_${mobId}`), "0");
}

const failure = makeConversation(0, 0.99);
for (let stageIndex = 0; stageIndex < stages.length; stageIndex++) satisfyKills(failure, stageIndex);
context.cm = failure.cm;
vm.runInContext("UPGRADE_SUCCESS_RATE = 0;", context);
removedEquipment.length = 0;
context.doArmorUpgrade();
assert.strictEqual(failure.values.get(`${context.STAGE_KEY_PREFIX}armor`), "-1");
assert.strictEqual(removedEquipment.length, 4, "failure must consume the previous set");
assert.strictEqual(failure.equips.length, 0, "failure must not grant target equipment");
assert.strictEqual(failure.getMesoDelta(), -15000000);
assert.strictEqual(failure.getCashDelta(), -2000);
for (let stageIndex = 0; stageIndex < stages.length; stageIndex++) {
    for (const [mobId] of stages[stageIndex].conditions.killMobs) {
        assert.strictEqual(failure.values.get(`${context.KILL_KEY_PREFIX}${stageIndex}_${mobId}`), "0");
    }
}
assert(failure.messages.some((message) => message.includes("从30级套装重新制作")));

const progress = fs.readFileSync(progressPath, "utf8");
assert(progress.includes('STAGE_KEY_PREFIX = "equip_upgrade_v2_stage_"'));
assert(progress.includes('KILL_KEY_PREFIX = "equip_upgrade_v2_kill_"'));
assert(progress.includes("int targetStage = completedStage + 1;"));
assert(progress.includes("STAGE_KILL_REQUIREMENTS.get(targetStage).get(mobId)"));
assert(progress.includes("if (current >= requiredCount)"), "kill counts must stop at their configured cap");
assert(!progress.includes("STAGE_MIN_LEVEL"), "old level-based kill routing must be removed");
assert(!progress.includes("weaponStage"), "removed weapon progression must not affect kill routing");

const javaRequirementBlocks = [...progress.matchAll(/requirements\(([^)]*)\)/gs)]
    .slice(0, stages.length)
    .map((match) => (match[1].match(/\d+/g) || []).map(Number));
assert.strictEqual(javaRequirementBlocks.length, stages.length);
for (let stageIndex = 0; stageIndex < stages.length; stageIndex++) {
    const expected = Array.from(stages[stageIndex].conditions.killMobs).flatMap((entry) => Array.from(entry));
    assert.deepStrictEqual(javaRequirementBlocks[stageIndex], expected,
        `Java kill requirements differ from JS stage ${stageIndex}`);
}

const monster = fs.readFileSync(monsterPath, "utf8");
assert(monster.includes("EquipmentEvolutionProgress.recordKill(attacker, getId())"));
assert(!monster.includes("EquipmentEvolutionProgress.recordBossClear"));

const drops = fs.readFileSync(dropPath, "utf8");
for (const [bossId, itemId, chance] of [
    [3220000, 4031543, 50000], [2220000, 4031543, 50000],
    [5220002, 4031544, 50000], [5220000, 4031545, 50000],
    [4130103, 1002006, 30000], [7220001, 1002761, 30000],
    [8130100, 1004556, 30000], [8220001, 1702598, 30000],
]) {
    assert(drops.includes(`(${bossId}, ${itemId}, 1, 1, 0, ${chance})`),
        `missing evolution drop ${bossId} -> ${itemId}`);
}

function findImgdirBlock(text, nodeName) {
    const startPattern = new RegExp(`<imgdir\\s+name="${nodeName}"(?:\\s[^>]*)?>`);
    const startMatch = startPattern.exec(text);
    assert(startMatch, `missing imgdir ${nodeName}`);
    const tagPattern = /<imgdir\b[^>]*>|<\/imgdir>/g;
    tagPattern.lastIndex = startMatch.index;
    let depth = 0;
    for (let match = tagPattern.exec(text); match; match = tagPattern.exec(text)) {
        if (match[0].startsWith("</")) {
            depth--;
            if (depth === 0) return text.slice(startMatch.index, tagPattern.lastIndex);
        } else if (!match[0].endsWith("/>")) {
            depth++;
        }
    }
    throw new Error(`unterminated imgdir ${nodeName}`);
}

for (const fileName of ["Check.img.xml", "Act.img.xml", "QuestInfo.img.xml", "Say.img.xml"]) {
    const base = fs.readFileSync(path.join(root, "gms-server/wz/Quest.wz", fileName), "utf8");
    const localized = fs.readFileSync(path.join(root, "gms-server/wz-zh-CN/Quest.wz", fileName), "utf8");
    assert.strictEqual(findImgdirBlock(localized, "-27916"), findImgdirBlock(base, "-27916"),
        `${fileName} quest -27916 differs between base and zh-CN`);
    assert(localized.indexOf('<imgdir name="-27916">') < localized.indexOf('<imgdir name="-27917">'),
        `${fileName} quest -27916 is not before its original sibling anchor`);
}

console.log("equipment evolution contract passed: 10 stages, stage-bound kills, reset-on-failure, drops and quest XML");
