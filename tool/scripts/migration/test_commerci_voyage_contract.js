#!/usr/bin/env node

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "../../..");

function areaMap() {
    const values = new Map();
    return {
        get(key) { return values.get(Number(key)); },
        put(key, value) { values.set(Number(key), String(value)); },
        values
    };
}

function javaStub(today) {
    return {
        type(name) {
            if (name === "java.lang.Short") return { valueOf(value) { return Number(value); } };
            if (name === "java.text.SimpleDateFormat") {
                return function SimpleDateFormat() { this.format = function format() { return today; }; };
            }
            if (name === "java.util.Date") return function DateStub() {};
            if (name === "java.awt.Point") return function Point(x, y) { this.x = x; this.y = y; };
            if (name === "org.gms.server.life.LifeFactory") return {};
            return function UnknownJavaType() {};
        },
        to(value) { return value; }
    };
}

function loadScript(relativePath, extra) {
    const sandbox = Object.assign({ console, Math, Java: javaStub("20260920") }, extra || {});
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(path.join(ROOT, relativePath), "utf8"), sandbox, { filename: relativePath });
    return sandbox;
}

function player(mapId) {
    const areas = areaMap();
    return {
        getAreaInfos() { return areas; },
        getMapId() { return mapId == null ? 865000001 : mapId; },
        getName() { return "Tester"; },
        areas
    };
}

function testTradeState() {
    const p = player(865000001);
    const npc = loadScript("gms-server/scripts/npc/9390220.js", { cm: { getPlayer() { return p; } } });
    const initial = npc.defaultState();
    assert.strictEqual(initial.energy, 100);
    assert.strictEqual(initial.energyCap, 100);
    assert.strictEqual(initial.cargoCap, 2);
    assert.strictEqual(initial.unlockMask, 1);
    assert.deepStrictEqual(Array.from(initial.stock), [6, 5, 4, 3, 1, 1]);

    initial.day = "20260919";
    initial.energy = 4;
    initial.stock = [0, 0, 0, 0, 0, 0];
    initial.cargo = [1, 0, 0, 0, 0, 0];
    p.areas.put(32010, npc.encodeState(initial));
    const reset = npc.loadState(p);
    assert.strictEqual(reset.day, "20260920");
    assert.strictEqual(reset.energy, 100);
    assert.deepStrictEqual(Array.from(reset.stock), [6, 5, 4, 3, 1, 1]);
    assert.deepStrictEqual(Array.from(reset.cargo), [1, 0, 0, 0, 0, 0]);

    reset.cargo = [1, 1, 0, 0, 0, 0];
    assert.strictEqual(npc.cargoUsed(reset), 2);
    assert.strictEqual(npc.cargoReward(reset, 0), 4);
    assert.strictEqual(npc.cargoReward(reset, 5), 23);
    reset.energy = 9;
    reset.unlockMask = 1;
    npc.saveState(p, reset);
    assert.match(npc.validateVoyageMember(p, 0), /能量不足/);
    reset.energy = 100;
    npc.saveState(p, reset);
    assert.match(npc.validateVoyageMember(p, 1), /尚未解锁/);
    reset.unlockMask = 3;
    npc.saveState(p, reset);
    assert.strictEqual(npc.validateVoyageMember(p, 1), null);
    assert.deepStrictEqual(Array.from(npc.routeEnergy), [10, 12, 15, 20, 25, 30]);
    assert.deepStrictEqual(Array.from(npc.routeExperience), [180, 300, 420, 1000, 1500, 2200]);
}

function activeState(route, reward, exp) {
    return [
        "C1", "20260920", "0", "1", "0", "90", "100", "2", "1",
        "0,0,0,0,0,0", "6,5,4,3,1,1", "0,0,0,0,0,0",
        "0", "0", "0", "0", "1", String(route), String(reward), String(exp), "2"
    ].join("|");
}

function testEventSettlement() {
    const event = loadScript("gms-server/scripts/event/CommerciVoyage.js");
    const p = player(865000400);
    p.areas.put(32010, activeState(3, 50, 1000));
    event.saveCompletedVoyage(p, 3, 80, false);
    let state = event.parseState(p.areas.get(32010));
    assert.strictEqual(state.pendingCoins, 40);
    assert.strictEqual(state.pendingExp, 1000);
    assert.strictEqual(Number(state.counts[3]), 1);
    assert.strictEqual(state.active, 0);

    p.areas.put(32010, activeState(3, 50, 1000));
    const originalRandom = event.Math.random;
    event.Math.random = function random() { return 0.99; };
    event.saveCompletedVoyage(p, 3, 100, true);
    event.Math.random = originalRandom;
    state = event.parseState(p.areas.get(32010));
    assert.strictEqual(state.pendingCoins, 50);
    assert.strictEqual(state.pendingExp, 1000);
    assert.deepStrictEqual(Array.from(event.routeMinutes), [3, 5, 7, 9, 11, 13]);
    assert.strictEqual(event.routeWaves.length, 6);
    assert.ok(event.routeWaves[3].some((wave) => wave.mob === 9390804));
    assert.deepStrictEqual(
        Array.from(event.routeWaves, (route) => Array.from(route, (wave) => wave.count)),
        [[9, 12, 3], [12, 12, 3], [12, 15, 3], [15, 15, 3, 3],
            [15, 15, 3, 15, 3], [15, 15, 3, 15, 3]]
    );
    assert.deepStrictEqual(Array.from(event.waterSpawnOffsets), [-400, 0, 400]);
    assert.strictEqual(event.waterSurfaceSearchY, 400);
    const waterSpawns = [];
    const waterMap = {
        getFootholds() {
            return { findBelow(point) { return { getId() { return point.x + 1000; } }; } };
        },
        spawnMonsterOnGroundBelow(monster, point) { waterSpawns.push([monster.fh, point.x, point.y]); }
    };
    for (let index = 0; index < 3; index++) {
        const monster = { setFh(fh) { this.fh = fh; } };
        event.spawnWaterMonster(waterMap, monster, { waterX: 320 }, index);
    }
    assert.deepStrictEqual(waterSpawns, [[920, -80, 400], [1320, 320, 400], [1720, 720, 400]]);
    assert.ok(event.bossLoot.includes(4007000));
    assert.ok(event.bossLoot.includes(5570000));
    assert.match(fs.readFileSync(path.join(ROOT, "gms-server/wz/Item.wz/Etc/0400.img.xml"), "utf8"), /name="04007000"/);
    assert.match(fs.readFileSync(path.join(ROOT, "gms-server/wz/Item.wz/Cash/0557.img.xml"), "utf8"), /name="05570000"/);

    const timedPlayer = player(865000100);
    timedPlayer.areas.put(32010, activeState(0, 10, 180));
    const props = { route: 0, wave: 0, finished: 0, bossDefeated: 0 };
    const actions = [];
    const eim = {
        getIntProperty(name) { return props[name] || 0; },
        setIntProperty(name, value) { props[name] = Number(value); },
        getPlayers() { return { size() { return 1; }, get() { return timedPlayer; } }; },
        dropMessage(type, message) { actions.push(message); },
        schedule(name, delay) { actions.push([name, delay]); },
        setEventCleared() { actions.push("cleared"); },
        stopEventTimer() { actions.push("timer-stopped"); }
    };
    event.completeVoyage(eim, false);
    state = event.parseState(timedPlayer.areas.get(32010));
    assert.strictEqual(state.pendingCoins, 7);
    assert.strictEqual(state.pendingExp, 180);
    assert.ok(actions.some((entry) => Array.isArray(entry) && entry[0] === "finishVoyage" && entry[1] === 3000));
}

function testClaimAndExchangeResources() {
    const p = player(865000001);
    p.areas.put(32010, [
        "C1", "20260920", "0", "1", "9900", "90", "100", "2", "1",
        "1,0,0,0,0,0", "6,5,4,3,1,1", "0,0,0,0,0,0",
        "12", "180", "1012438", "1", "0", "-1", "0", "0", "0"
    ].join("|"));
    const gained = [];
    const cm = {
        getPlayer() { return p; },
        canHold() { return true; },
        gainItem(id, quantity) { gained.push([Number(id), Number(quantity)]); },
        sendOk() {},
        dispose() {},
        itemQuantity() { return 0; }
    };
    const exchange = loadScript("gms-server/scripts/npc/9390221.js", { cm });
    exchange.claimVoyage();
    const saved = exchange.loadState();
    assert.strictEqual(saved.level, 2);
    assert.strictEqual(saved.exp, 80);
    assert.strictEqual(saved.pendingCoins, 0);
    assert.deepStrictEqual(gained, [[4310100, 12], [1012438, 1]]);

    const weaponIds = [1302297, 1312173, 1322223, 1332247, 1372195, 1382231,
        1402220, 1412152, 1422158, 1432187, 1442242, 1452226, 1462213,
        1472235, 1482189, 1492199];
    assert.deepStrictEqual(
        Array.from(exchange.exchanges.filter((offer) => weaponIds.includes(offer.item)), (offer) => offer.item),
        weaponIds
    );
    assert.ok(exchange.exchanges.filter((offer) => weaponIds.includes(offer.item)).every((offer) => offer.price === 400));

    for (const offer of exchange.exchanges) {
        const padded = String(offer.item).padStart(8, "0");
        const prefix = Math.floor(offer.item / 10000);
        const category = prefix >= 130 && prefix <= 149 ? "Weapon" :
            prefix === 110 ? "Cape" : prefix === 108 ? "Glove" :
            prefix === 107 ? "Shoes" : prefix === 105 ? "Longcoat" :
            prefix === 100 ? "Cap" : "Accessory";
        assert.ok(fs.existsSync(path.join(ROOT, "clien/Data/Character", category, padded + ".img")), offer.name);
        assert.ok(fs.existsSync(path.join(ROOT, "gms-server/wz/Character.wz", category, padded + ".img.xml")), offer.name);
    }
}

testTradeState();
testEventSettlement();
testClaimAndExchangeResources();
console.log("Commerci voyage contract checks passed");
