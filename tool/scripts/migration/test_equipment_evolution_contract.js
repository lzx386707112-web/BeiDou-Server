#!/usr/bin/env node

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "../../..");
const scriptPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/装备制作/套装进化.js");
const menuPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/装备制作/装备制作.js");
const weaponCraftPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/装备制作/武器制作.js");
const teleportPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/万能传送.js");
const mainQuestPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/任务/主线任务.js");
const oreCraftPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/矿石合成.js");
const gradedGemPath = path.join(root, "gms-server/scripts-zh-CN/BeiDouSpecial/高等宝石兑换.js");
const progressPath = path.join(root, "gms-server/src/main/java/org/gms/server/EquipmentEvolutionProgress.java");
const monsterPath = path.join(root, "gms-server/src/main/java/org/gms/server/life/Monster.java");
const alienDropPath = path.join(root,
    "gms-server/src/main/resources/db/migration/V2.0.4__boss_9600087_alien_drops.sql");
const source = fs.readFileSync(scriptPath, "utf8");
const context = {Java: {type: () => ({})}};
vm.createContext(context);
vm.runInContext(source, context, {filename: scriptPath});

const recipes = Array.from(context.setRecipes);
assert.strictEqual(recipes.length, 178, "unexpected full-set progression recipe count");
const expectedRecipesByJob = [74, 26, 26, 26, 26];
for (let job = 0; job < 5; job++) {
    assert.strictEqual(recipes.filter((recipe) => recipe.jobIndex === job).length, expectedRecipesByJob[job]);
}

const identity = new Set();
for (const recipe of recipes) {
    const canonicalSources = Array.from(recipe.sourceOptions, (options) => options[0]);
    const key = [canonicalSources.join(","), recipe.jobIndex, recipe.route].join(":");
    assert(!identity.has(key), `duplicate recipe ${key}`);
    identity.add(key);
    assert(recipe.rule.materials.length > 0, `recipe ${key} has no material cost`);
    assert.strictEqual(recipe.sourceOptions.length, 6, `recipe ${key} must consume a six-piece set`);
    assert([6, 7].includes(recipe.targetIds.length), `recipe ${key} has an invalid target set size`);
}

assert.deepStrictEqual(Array.from(context.STARTER_RULE.materials[0]), [4000032, 30]);
assert.strictEqual(context.STARTER_RULE.materials.length, 4);
assert.strictEqual(context.STARTER_RULE.meso, 300000);
assert(context.STARTER_RULE.quests.includes(600003), "starter set must retain the main-quest gate");

const firstSet = recipes.find((recipe) => recipe.sourceOptions[0][0] === 1302169 && recipe.jobIndex === 0);
assert.deepStrictEqual(Array.from(context.getSetCosts(firstSet).materials[0]), [4000000, 40]);
assert.strictEqual(context.getSetCosts(firstSet).meso, 1300000);
assert.strictEqual(context.getCurrentChance({rule: {chance: 35, pity: 10}}, 5), 60);
assert.strictEqual(context.getCurrentChance({rule: {chance: 35, pity: 10}}, 10), 100);

function mockEquip(initial) {
    const values = {...initial};
    const result = {values};
    const properties = [
        "Str", "Dex", "Int", "Luk", "Hp", "Mp", "Watk", "Matk", "Wdef", "Mdef",
        "Acc", "Avoid", "Hands", "Speed", "Jump", "Vicious", "UpgradeSlots", "LevelExpand",
        "Level", "ItemLevel", "ItemExp", "Owner", "Flag", "Expiration", "GiftFrom",
        "UpgradeHistory", "ChaosHistory", "AbsorbHistory", "CombinationType", "ExpandAttribute1",
        "ExpandAttribute2", "ExpandAttribute3", "ExpandAttribute4", "MaxStar", "StarLevel",
        "StarCount", "UpgradeResetCount", "UpgradeReturn",
    ];
    for (const property of properties) {
        result[`get${property}`] = () => values[property] ?? (typeof values[property] === "string" ? "" : 0);
        result[`set${property}`] = (value) => { values[property] = value; };
    }
    return result;
}

const sourceTemplate = mockEquip({Str: 10, Watk: 20, UpgradeSlots: 7});
const sourceEquip = mockEquip({
    Str: 15, Watk: 27, UpgradeSlots: 4, Level: 3, LevelExpand: 0,
    ItemLevel: 4, Owner: "owner", Flag: 1, StarLevel: 6, UpgradeHistory: "history",
});
const targetEquip = mockEquip({Str: 100, Watk: 200, UpgradeSlots: 12});
context.inheritEquipment(sourceEquip, sourceTemplate, targetEquip);
assert.strictEqual(targetEquip.values.Str, 105);
assert.strictEqual(targetEquip.values.Watk, 207);
assert.strictEqual(targetEquip.values.UpgradeSlots, 9);
assert.strictEqual(targetEquip.values.Level, 3);
assert.strictEqual(targetEquip.values.Owner, "owner");
assert.strictEqual(targetEquip.values.StarLevel, 6);

const weaponTarget = mockEquip({UpgradeSlots: 12, LevelExpand: 0, MaxStar: 0});
context.inheritEquipment(sourceEquip, sourceTemplate, weaponTarget, {levelExpand: 10, maxStar: 50});
assert.strictEqual(weaponTarget.values.LevelExpand, 10);
assert.strictEqual(weaponTarget.values.MaxStar, 50);
assert.strictEqual(weaponTarget.values.UpgradeSlots, 19);

const finalSet = recipes.find((recipe) => recipe.sourceOptions[0][0] === 1302343 && recipe.jobIndex === 0);
assert.strictEqual(finalSet.targetIds.length, 7);
assert.deepStrictEqual(Array.from(finalSet.targetIds.slice(1, 4)), [1005980, 1042433, 1062285]);
assert.deepStrictEqual(Array.from(finalSet.inheritFrom), [0, 1, 2, -1, 3, 4, 5]);

assert.deepStrictEqual(Array.from(context.WEAPON_PATHS, (paths) => paths.length), [8, 2, 2, 2, 2]);
const weaponPaths = Array.from(context.WEAPON_PATHS).flatMap((paths) => Array.from(paths));
assert.strictEqual(weaponPaths.length, 16, "all supported weapon types must share one progression");
for (let job = 0; job < 5; job++) {
    const royalWeapon = context.BRANCH_SETS.royal.items[job][0];
    const royalRecipes = recipes.filter((entry) => entry.sourceOptions[0][0] === royalWeapon && entry.jobIndex === job);
    assert.strictEqual(royalRecipes.length, context.WEAPON_PATHS[job].length);
    assert.deepStrictEqual(Array.from(new Set(royalRecipes.map((entry) => entry.targetIds[0]))).sort(),
        Array.from(context.VISITOR_ALIEN_SET.weapons[job]).sort(),
        `royal weapon for job ${job} does not lead through every hybrid weapon`);
    for (const recipe of royalRecipes) {
        assert.strictEqual(recipe.levelExpand, 0);
        assert.strictEqual(recipe.maxStar, 0);
    }
}

const royalSetRecipe = recipes.find((entry) => entry.jobIndex === 0
    && entry.sourceOptions[0][0] === context.BRANCH_SETS.royal.items[0][0]);
const substituteIds = Array.from(royalSetRecipe.sourceOptions, (options) => options[0]);
substituteIds[1] = 1004637;
substituteIds[4] = 1072737;
substituteIds[5] = 1102476;
const substituteItems = new Map(substituteIds.map((itemId) => [itemId, {getItemId: () => itemId}]));
context.cm = {
    getPlayer: () => ({
        getInventory: () => ({findById: (itemId) => substituteItems.get(itemId) || null}),
    }),
};
const matchedSubstituteSet = context.findSourceSet(royalSetRecipe, null);
assert.deepStrictEqual(Array.from(matchedSubstituteSet, (item) => item.getItemId()), substituteIds);
assert.strictEqual(context.formatSetPreview([1003242, 1052357]), "#v1003242##v1052357#");
for (const pathEntry of weaponPaths) {
    assert.strictEqual(pathEntry.items.length, 5, `incomplete weapon path ${pathEntry.name}`);
    for (let stage = 1; stage < pathEntry.items.length; stage++) {
        const recipe = recipes.find((entry) => entry.sourceOptions[0][0] === pathEntry.items[stage - 1]
            && entry.targetIds[0] === pathEntry.items[stage]);
        assert(recipe, `missing unified weapon transition ${pathEntry.items[stage - 1]} -> ${pathEntry.items[stage]}`);
        assert.strictEqual(recipe.levelExpand, context.WEAPON_LEVEL_EXPAND[stage]);
        assert.strictEqual(recipe.maxStar, context.WEAPON_MAX_STAR[stage]);
    }
}
for (let job = 0; job < 5; job++) {
    for (let pathIndex = 0; pathIndex < context.WEAPON_PATHS[job].length; pathIndex++) {
        const pathEntry = context.WEAPON_PATHS[job][pathIndex];
        const hybridItems = Array.from(context.getVisitorAlienSetItems(job, pathIndex));
        assert.deepStrictEqual(hybridItems.slice(1), [1003540, 1052460, 1082432, 1072664, 1132040]);
        assert.strictEqual(hybridItems[0], context.VISITOR_ALIEN_SET.weapons[job][pathIndex]);
        const hybridRecipe = recipes.find((entry) => entry.jobIndex === job
            && entry.sourceOptions[0][0] === context.BRANCH_SETS.royal.items[job][0]
            && entry.targetIds[0] === hybridItems[0]);
        assert(hybridRecipe, `missing Royal Lion -> Visitor/Alien transition for ${pathEntry.name}`);
        assert.deepStrictEqual(Array.from(hybridRecipe.inheritFrom), [0, 1, 2, 3, 4, 5]);
        assert.strictEqual(hybridRecipe.sourceOptions[5][0], context.BRANCH_SETS.royal.items[job][5]);
        assert.strictEqual(hybridRecipe.targetIds[5], 1132040, "Royal cape must transfer into the hybrid belt slot");
        const branchRecipes = recipes.filter((entry) => entry.jobIndex === job
            && entry.sourceOptions[0][0] === hybridItems[0]
            && entry.targetIds[0] === pathEntry.items[0]);
        assert.strictEqual(branchRecipes.length, 2,
            `hybrid ${pathEntry.name} must branch to both Pensalir and Empress armor`);
        for (const recipe of branchRecipes) {
            assert.deepStrictEqual(Array.from(recipe.inheritFrom), [0, 1, 2, 3, 4, 5]);
            assert.strictEqual(recipe.sourceOptions[5][0], 1132040);
            assert([context.BRANCH_SETS.pensalir.items[job][5], context.BRANCH_SETS.empress.items[job][5]]
                .includes(recipe.targetIds[5]), "hybrid belt must transfer back into the branch cape slot");
            assert.strictEqual(recipe.levelExpand, context.WEAPON_LEVEL_EXPAND[0]);
            assert.strictEqual(recipe.maxStar, context.WEAPON_MAX_STAR[0]);
        }
    }
}

const weaponCraftSource = fs.readFileSync(weaponCraftPath, "utf8");
const weaponCraftContext = {Java: {type: () => ({})}};
vm.createContext(weaponCraftContext);
vm.runInContext(weaponCraftSource, weaponCraftContext, {filename: weaponCraftPath});
const weaponCraftNames = [
    "拳套", "短刀", "长杖", "弓", "弩", "爪子", "短枪", "双手剑",
    "单手剑", "双手斧", "单手斧", "单手锤子", "双手锤子", "长枪", "矛",
];
for (const name of weaponCraftNames) {
    const oldTargets = Array.from(weaponCraftContext[name], (entry) => entry.id);
    assert(weaponPaths.some((entry) => oldTargets.every((itemId, index) => entry.items[index] === itemId)),
        `old weapon crafting path ${name} is not preserved`);
}

const sharedBridgeSources = [1004637, 1003621, 1072239, 1072344, 1072732, 1072737, 1072743];
for (let job = 0; job < 5; job++) {
    for (const sourceId of sharedBridgeSources) {
        assert(recipes.some((entry) => entry.jobIndex === job
            && entry.sourceOptions.some((options) => Array.from(options).includes(sourceId))),
        `missing crafted equipment substitute ${sourceId} for job ${job}`);
    }
    for (const sourceId of [1102471 + job, 1102476 + job, 1102481 + job]) {
        assert(recipes.some((entry) => entry.jobIndex === job
            && entry.sourceOptions.some((options) => Array.from(options).includes(sourceId))),
        `missing crafted cape substitute ${sourceId}`);
    }
}

function equipmentPath(itemId, client) {
    const prefix = Math.floor(itemId / 10000);
    const category = prefix === 100 ? "Cap"
        : prefix === 103 || prefix === 112 || prefix === 113 ? "Accessory"
        : prefix === 104 ? "Coat"
        : prefix === 105 ? "Longcoat"
        : prefix === 106 ? "Pants"
        : prefix === 107 ? "Shoes"
        : prefix === 108 ? "Glove"
        : prefix === 110 ? "Cape"
        : "Weapon";
    const file = String(itemId).padStart(8, "0") + ".img" + (client ? "" : ".xml");
    return path.join(root, client ? "clien/Data/Character" : "gms-server/wz/Character.wz", category, file);
}

const equipmentIds = new Set();
for (const recipe of recipes) {
    recipe.sourceOptions.forEach((options) => options.forEach((itemId) => equipmentIds.add(itemId)));
    recipe.targetIds.forEach((itemId) => equipmentIds.add(itemId));
}
for (const itemId of equipmentIds) {
    assert(fs.existsSync(equipmentPath(itemId, true)), `missing client equipment ${itemId}`);
    assert(fs.existsSync(equipmentPath(itemId, false)), `missing server equipment ${itemId}`);
}

const materialIds = new Set(context.STARTER_RULE.materials.map((entry) => entry[0]));
const stageThemes = new Set();
const categorySignatures = new Set();

function materialCategory(itemId) {
    if ([4000000, 4000016, 4000019].includes(itemId)) return "snail-hunt";
    if ([4000020, 4000021, 4000030].includes(itemId)) return "hide-hunt";
    if ([4000073, 4000074, 4000079, 4000229, 4000283, 4000289].includes(itemId)) return "regional-trophy";
    if ([4003000, 4003001].includes(itemId)) return "workshop-part";
    if ([4000313, 4001126].includes(itemId)) return "quest-reward";
    if ([4001198, 4001246, 4032266].includes(itemId)) return "party-quest-token";
    if (itemId === 4032474) return "boss-trophy";
    if (itemId === 4032133) return "alien-boss-crystal";
    if (itemId >= 4005000 && itemId <= 4005004) return "stat-crystal";
    if (itemId >= 4011000 && itemId < 4012000) return "refined-ore";
    if (itemId === 4021010) return "time-stone";
    if (itemId >= 4021000 && itemId < 4022000) return "refined-jewel";
    if (itemId >= 4250000 && itemId < 4260000) return `graded-gem-${itemId % 10}`;
    if (itemId === 4260009) return "boss-gem";
    if (itemId === 2435719) return "core-gemstone";
    return "monster-drop";
}

for (const [stage, rule] of Array.from(context.STEP_RULES).entries()) {
    assert(rule.materials.length >= 4, "every evolution stage must mix at least four materials");
    assert(rule.theme && !stageThemes.has(rule.theme), `stage ${stage} has a missing or duplicate gameplay theme`);
    stageThemes.add(rule.theme);
    const signature = [...new Set(Array.from(rule.materials, (entry) => materialCategory(entry[0])))].sort().join("+");
    assert(!categorySignatures.has(signature), `stage ${stage} repeats material category template ${signature}`);
    categorySignatures.add(signature);
    for (const entry of rule.materials) {
        materialIds.add(entry[0]);
        assert(!(entry[0] >= 4260000 && entry[0] <= 4260008),
            `monster crystal ${entry[0]} must not remain mandatory`);
    }
}
assert.strictEqual(stageThemes.size, 17);
assert.deepStrictEqual(Array.from(context.STEP_RULES[9].bosses), [6090002, 7220001],
    "Akayrum must not block the Royal Lion stage");
assert.deepStrictEqual(Array.from(context.STEP_RULES[10].bosses || []), [],
    "the hybrid stage must not force the 2.1B HP Drill boss");
assert.deepStrictEqual(Array.from(context.STEP_RULES[13].bosses), [8220002, 8220009, 8860000],
    "Akayrum must remain in the late high-tier weapon transition");
assert.deepStrictEqual(Array.from(context.STEP_RULES[14].bosses), [8220003, 8910100, 8900100, 8920100, 8930100],
    "Root Abyss must remain in the late Absolab armor transition");
assert.deepStrictEqual(Array.from(context.STEP_RULES[15].bosses || []), [],
    "Arcane River progression must use quests instead of an unrelated boss gate");
assert(context.STEP_RULES[15].materials.find((entry) => entry[0] === 2435719)[1] <= 15);
assert(context.STEP_RULES[16].materials.find((entry) => entry[0] === 2435719)[1] <= 30);
assert(context.STEP_RULES[16].materials.find((entry) => entry[0] === 4021010)[1] <= 3);

for (const itemId of materialIds) {
    const prefix = String(itemId).padStart(8, "0").slice(0, 4);
    const category = itemId >= 2000000 && itemId < 3000000 ? "Consume" : "Etc";
    const relative = `gms-server/wz/Item.wz/${category}/${prefix}.img.xml`;
    const xml = fs.readFileSync(path.join(root, relative), "utf8");
    assert(xml.includes(`name="0${itemId}"`), `missing server material ${itemId}`);
    assert(fs.existsSync(path.join(root, `clien/Data/Item/${category}/${prefix}.img`)),
        `missing client material group ${prefix}`);
}

const customMainQuest = fs.readFileSync(mainQuestPath, "utf8");
assert(customMainQuest.includes("var 基础任务ID = 600001"), "custom main quest base ID changed");
assert(/var 等级 = \[10, 30, 50, 70, 90, 120, 140\]/.test(customMainQuest), "custom main quest stages changed");
for (const questId of [600003, 600004, 600005, 600006, 600007]) {
    assert(source.includes(String(questId)), `missing custom main quest requirement ${questId}`);
}

const questFiles = ["Check", "Act", "Say"].map((name) =>
    fs.readFileSync(path.join(root, `gms-server/wz/Quest.wz/${name}.img.xml`), "utf8")
);
for (const questId of [31180, 34102, 34103, 34104, 34105]) {
    for (const questXml of questFiles) {
        assert(questXml.includes(`<imgdir name="${questId}">`), `incomplete WZ quest ${questId}`);
    }
}

const oldDropData = fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V1.0.51__drop_data_insert_old_data.sql"), "utf8");
const regularDropMaterials = [...materialIds].filter((itemId) =>
    (itemId >= 4000000 && itemId < 4030000)
        && ![4000313, 4001126, 4001198, 4001246, 4021010].includes(itemId)
);
for (const itemId of regularDropMaterials) {
    assert(oldDropData.includes(`, ${itemId},`), `missing normal-monster or ore drop ${itemId}`);
}
for (const [bossId, itemId] of [[4220001, 4032474], [7220000, 4000283], [7220002, 4000289],
    [8220000, 4000073], [8220000, 4000074]]) {
    assert(oldDropData.includes(`(${bossId}, ${itemId}, 1, 1, 0,`),
        `missing unconditional themed boss drop ${bossId} -> ${itemId}`);
}
const alienDropSource = fs.readFileSync(alienDropPath, "utf8");
for (const bossId of [8840000, 9600087]) {
    assert(alienDropSource.includes(`VALUES (${bossId}, 4032133, 3, 3, 0, 99900)`),
        `missing Red Diamond production from boss ${bossId}`);
}
const globalDrops = fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V1.0.50__drop_data_global_insert_old_data.sql"), "utf8");
assert(globalDrops.includes("4001126"), "missing global Maple Leaf production");
assert(customMainQuest.includes("[1, 10, 5]"), "main quest no longer awards Golden Maple Leaves");

const oreCraftSource = fs.readFileSync(oreCraftPath, "utf8");
for (const itemId of [4003000, 4003001, 4005000, 4005001, 4005002, 4005003, 4005004,
    4011000, 4011001, 4011007, 4021001, 4021003, 4021008, 4021009, 4251200]) {
    assert(oreCraftSource.includes(String(itemId)), `material ${itemId} is not available from ore crafting`);
}
const gradedGemSource = fs.readFileSync(gradedGemPath, "utf8");
for (const itemId of [4250000, 4250001, 4250002, 4250800, 4250801, 4250900, 4250901,
    4251000, 4251001, 4251100, 4251101, 4251300, 4251301, 4251302, 4251401]) {
    assert(gradedGemSource.includes(String(itemId)), `graded gem ${itemId} has no conversion recipe`);
}
for (const [relativePath, itemId] of [
    ["gms-server/scripts-zh-CN/npc/2133001.js", 4001198],
    ["gms-server/scripts-zh-CN/npc/2040035.js", 4001246],
    ["gms-server/scripts-zh-CN/npc/2094001.js", 4032266],
]) {
    const pqRewardSource = fs.readFileSync(path.join(root, relativePath), "utf8");
    assert(pqRewardSource.includes(`gainItem(${itemId}, 1)`), `party quest reward ${itemId} has no repeatable grant`);
}
const bossMaterialDrops = fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V2.1.49__add_equipment_evolution_boss_material_drops.sql"), "utf8");
for (const itemId of [4260009]) {
    assert(bossMaterialDrops.includes(`, ${itemId},`), `missing boss production for material ${itemId}`);
}
assert(fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V2.1.45__add_arcane_river_core_gemstone_drop.sql"), "utf8")
    .includes("2435719"), "missing Core Gemstone production");
assert(fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V2.1.28__add_shenshuo_eight_boss_drops.sql"), "utf8")
    .includes("4021010"), "missing Time Stone production");
const crystalMigration = fs.readFileSync(path.join(root,
    "gms-server/src/main/resources/db/migration/V2.1.48__add_equipment_evolution_crystal_drops.sql"), "utf8");
for (let itemId = 4260000; itemId <= 4260008; itemId++) {
    assert(crystalMigration.includes(`, ${itemId}, `), `missing generated drops for crystal ${itemId}`);
}

const menu = fs.readFileSync(menuPath, "utf8");
assert(menu.includes('openNpc("装备制作/套装进化")'));
assert(menu.includes("整套装备进化"));
assert(!menu.includes('openNpc("装备制作/武器制作")'), "standalone weapon path must not remain reachable");
assert(!/\bwarp(?:Party|Map)?\s*\(/.test(source), "evolution NPC must not warp risky maps");
assert(source.includes("source[\"get\" + name]() - sourceTemplate[\"get\" + name]()"));
assert(source.includes("BRANCH_SETS.eternalPants.items[jobIndex]"));
assert(source.includes("整套进化要求六件装备都放在装备栏"));
assert(context.VISITOR_ALIEN_SLOT_NOTE.includes("皇家斗篷的强化会继承到腰带"),
    "hybrid cape-to-belt inheritance must be explained");
assert(source.includes("formatSetPreview"), "equipment icon previews are missing");
assert(source.includes("showPreviewMenu"), "full progression preview menu is missing");

const progress = fs.readFileSync(progressPath, "utf8");
const progressionBosses = [
    2220000, 9400610, 9400609, 9400613, 9400612, 9400611, 9400633,
    3220000, 3220001, 4220001, 5220002, 5220004, 5220001, 5220003,
    6220000, 6220001, 6090002, 7220001, 7220000, 7220002,
    8220000, 8220002, 8220009, 8220003,
    8860000, 8850011, 8910100, 8900100, 8920100, 8930100,
    8870000, 8870200, 8880400, 8880200, 8645009, 8880700, 8880803,
];
const stagedBosses = Array.from(context.STEP_RULES)
    .flatMap((rule) => Array.from(rule.bosses || []));
assert.strictEqual(new Set(stagedBosses).size, stagedBosses.length,
    "qualification bosses must not be repeated across evolution stages");
assert.deepStrictEqual([...stagedBosses].sort((a, b) => a - b),
    [...progressionBosses].sort((a, b) => a - b),
    "every permanent qualification boss must appear in exactly one evolution stage");
for (const bossId of progressionBosses) {
    assert(progress.includes(String(bossId)), `missing permanent boss qualification ${bossId}`);
    assert(bossMaterialDrops.includes(`(${bossId}, 4260009,`),
        `missing strengthening gem drop for qualification boss ${bossId}`);
}

const areaBossDir = path.join(root, "gms-server/scripts-zh-CN/event");
const areaBossFiles = fs.readdirSync(areaBossDir).filter((name) => /^AreaBoss.*\.js$/.test(name));
assert.strictEqual(areaBossFiles.length, 27, "unexpected active area boss script count");
const uniqueAreaBosses = new Set();
const teleport = fs.readFileSync(teleportPath, "utf8");
for (const fileName of areaBossFiles) {
    const eventSource = fs.readFileSync(path.join(areaBossDir, fileName), "utf8");
    const mapId = Number(eventSource.match(/var MapID = ([0-9]+);/)[1]);
    const bossId = Number(eventSource.match(/var BossID = ([0-9]+);/)[1]);
    uniqueAreaBosses.add(bossId);
    assert(teleport.includes(`Array(${mapId},`), `area boss map ${mapId} is not reachable from wild boss teleport`);
    assert(progressionBosses.includes(bossId), `area boss ${bossId} is not used by progression`);
    assert(context.STEP_RULES.some((rule) => (rule.bosses || []).includes(bossId)),
        `area boss ${bossId} has no progression stage`);

    const paddedMap = String(mapId).padStart(9, "0");
    const mapGroup = `Map${paddedMap[0]}`;
    const paddedBoss = String(bossId).padStart(7, "0");
    assert(fs.existsSync(path.join(root, `gms-server/wz/Map.wz/Map/${mapGroup}/${paddedMap}.img.xml`)),
        `missing server area boss map ${mapId}`);
    assert(fs.existsSync(path.join(root, `clien/Data/Map/Map/${mapGroup}/${paddedMap}.img`)),
        `missing client area boss map ${mapId}`);
    assert(fs.existsSync(path.join(root, `gms-server/wz/Mob.wz/${paddedBoss}.img.xml`)),
        `missing server area boss ${bossId}`);
    assert(fs.existsSync(path.join(root, `clien/Data/Mob/${paddedBoss}.img`)),
        `missing client area boss ${bossId}`);
}
assert.strictEqual(uniqueAreaBosses.size, 24, "duplicate area boss spawns must share one qualification");
const monster = fs.readFileSync(monsterPath, "utf8");
assert(monster.includes("EquipmentEvolutionProgress.recordBossClear(attacker, getId())"),
    "boss qualification is not connected to experience-awarding kills");

console.log(`equipment evolution contract passed: ${recipes.length} recipes, ${equipmentIds.size} equipment resources, ${uniqueAreaBosses.size} area bosses`);
