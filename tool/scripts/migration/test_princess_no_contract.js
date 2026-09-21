#!/usr/bin/env node

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "../../..");

function loadScript(relativePath, extra) {
    const Java = {
        type() { return function JavaType() {}; },
        to(value) { return value; }
    };
    const sandbox = Object.assign({ Java }, extra || {});
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(path.join(ROOT, relativePath), "utf8"), sandbox, {
        filename: relativePath
    });
    return sandbox;
}

function member(mapId, level, leader) {
    return {
        getMapId() { return mapId; },
        getLevel() { return level; },
        isLeader() { return leader; }
    };
}

function party(members) {
    return {
        size() { return members.length; },
        toArray() { return members; },
        getPartyMembersOnline() {
            return {
                size() { return members.length; },
                get(index) { return members[index]; }
            };
        },
        setEligibleMembers(value) { this.eligibleMembers = value; }
    };
}

function javaList(values) {
    return {
        size() { return values.length; },
        get(index) { return values[index]; }
    };
}

function testLocalizedEventMirror() {
    const base = fs.readFileSync(path.join(ROOT, "gms-server/scripts/event/PrincessNoBattle.js"), "utf8");
    const localized = fs.readFileSync(path.join(ROOT, "gms-server/scripts-zh-CN/event/PrincessNoBattle.js"), "utf8");
    assert.strictEqual(localized, base, "zh-CN event script must mirror the base event script");
}

function testLocalizedDailyNpcMirror() {
    const base = fs.readFileSync(path.join(ROOT, "gms-server/scripts/npc/9130000.js"), "utf8");
    const localized = fs.readFileSync(path.join(ROOT, "gms-server/scripts-zh-CN/npc/9130000.js"), "utf8");
    assert.strictEqual(localized, base, "zh-CN daily NPC script must mirror the base script");
}

function testEligibleParty() {
    const event = loadScript("gms-server/scripts/event/PrincessNoBattle.js");
    const valid = party([member(811000999, 160, true), member(811000999, 255, false)]);
    assert.strictEqual(event.getEligibleParty(valid).length, 2);
    assert.strictEqual(event.getEligibleParty(party([member(811000100, 200, true)])).length, 0);
    assert.strictEqual(event.getEligibleParty(party([member(811000999, 159, true)])).length, 0);
    assert.strictEqual(event.getEligibleParty(party([member(811000999, 200, false)])).length, 0);
}

function testFinalStageTransition() {
    const spawned = [];
    const changedMaps = [];
    const maps = new Map();
    const Point = function Point(x, y) { this.x = x; this.y = y; };
    const Java = {
        type(name) {
            if (name == "org.gms.server.life.LifeFactory") {
                return { getMonster(id) { return { id }; } };
            }
            if (name == "java.awt.Point") return Point;
            return function JavaType() {};
        },
        to(value) { return value; }
    };
    function map(mapId) {
        if (!maps.has(mapId)) {
            maps.set(mapId, {
                spawnMonsterOnGroundBelow(monster, point) {
                    spawned.push({ mapId, monsterId: monster.id, x: point.x, y: point.y });
                }
            });
        }
        return maps.get(mapId);
    }
    const player = {
        changeMap(target) { changedMaps.push(target.mapId); }
    };
    const eim = {
        stage: 3,
        getIntProperty() { return this.stage; },
        setIntProperty(name, value) { if (name == "stage") this.stage = value; },
        getInstanceMap(mapId) { return map(mapId); },
        getMapInstance(mapId) { return { mapId }; },
        getPlayers() { return javaList([player]); }
    };
    const event = loadScript("gms-server/scripts/event/PrincessNoBattle.js", { Java });
    event.monsterKilled({ getId() { return 9450039; } }, eim);
    assert.strictEqual(eim.stage, 4);
    assert.deepStrictEqual(spawned, [
        { mapId: 811000500, monsterId: 9450040, x: 0, y: -235 }
    ]);
    assert.deepStrictEqual(changedMaps, [811000500]);
}

function runNpc(options) {
    const messages = [];
    const calls = [];
    const members = options.members || [member(811000999, 200, true)];
    const currentParty = options.solo ? null : party(members);
    const eventManager = {
        getEligibleParty(value) {
            const eligible = members.filter((entry) => entry.getMapId() == 811000999
                && entry.getLevel() >= 160 && entry.getLevel() <= 255);
            const result = eligible.some((entry) => entry.isLeader()) ? eligible : [];
            value.setEligibleMembers(result);
            calls.push("eligible");
            return javaList(result);
        },
        startInstance() {
            assert.ok(currentParty == null || currentParty.eligibleMembers);
            calls.push("start");
            return options.started !== false;
        }
    };
    const player = { getMap() { return {}; } };
    const cm = {
        sendYesNo(message) { messages.push(message); },
        sendOk(message) { messages.push(message); },
        dispose() { calls.push("dispose"); },
        getEventManager() { return eventManager; },
        getParty() { return currentParty; },
        getPlayer() { return player; },
        isLeader() { return options.leader !== false; },
        haveItem(itemId, quantity) {
            assert.strictEqual(itemId, 4000699);
            assert.strictEqual(quantity, 1);
            return options.hasTicket !== false;
        },
        gainItem(itemId, quantity) { calls.push(`gain:${itemId}:${quantity}`); }
    };
    const npc = loadScript("gms-server/scripts/npc/9130100.js", { cm });
    npc.start();
    npc.action(1, 0, 0);
    return { calls, messages };
}

function testNpcEntry() {
    let result = runNpc({});
    assert.ok(result.calls.includes("eligible"));
    assert.ok(result.calls.includes("start"));
    assert.ok(!result.messages.some((message) => message.includes("已有队伍")));
    assert.ok(result.calls.includes("gain:4000699:-1"));

    result = runNpc({ hasTicket: false });
    assert.ok(result.messages.some((message) => message.includes("4000699")));
    assert.ok(!result.calls.includes("start"));
    assert.ok(!result.calls.some((call) => call.startsWith("gain:")));

    result = runNpc({ leader: false });
    assert.ok(result.messages.some((message) => message.includes("请让队长")));
    assert.ok(!result.calls.includes("start"));
    assert.ok(!result.calls.some((call) => call.startsWith("gain:")));

    result = runNpc({ members: [member(811000100, 200, true)] });
    assert.ok(result.messages.some((message) => message.includes("当前地图")));
    assert.ok(!result.calls.includes("start"));

    result = runNpc({ members: [member(811000999, 159, true)] });
    assert.ok(result.messages.some((message) => message.includes("160级")));
    assert.ok(!result.calls.includes("start"));

    result = runNpc({ started: false });
    assert.ok(result.messages.some((message) => message.includes("已有队伍")));
    assert.strictEqual(result.calls.filter((call) => call == "start").length, 1);
    assert.ok(!result.calls.some((call) => call.startsWith("gain:")));

    result = runNpc({ solo: true });
    assert.ok(result.calls.includes("start"));
    assert.ok(result.calls.includes("gain:4000699:-1"));
}

function runDailyNpc(options) {
    const messages = [];
    const calls = [];
    let completed = false;
    const quest = {
        canComplete() { return !completed; },
        canStart() { return false; },
        complete() { completed = true; calls.push("complete"); },
        start() { calls.push("startQuest"); }
    };
    const Java = {
        type(name) {
            assert.strictEqual(name, "org.gms.server.quest.Quest");
            return { getInstance(id) { assert.strictEqual(id, -8055); return quest; } };
        },
        to(value) { return value; }
    };
    const cm = {
        sendSimple(message) { messages.push(message); },
        sendYesNo(message) { messages.push(message); },
        sendOk(message) { messages.push(message); },
        dispose() { calls.push("dispose"); },
        getPlayer() { return {}; },
        getQuestStatus() { return 0; },
        isQuestCompleted() { return false; },
        canHold(itemId, quantity) {
            calls.push(`canHold:${itemId}:${quantity}`);
            return options.canHold !== false;
        },
        gainItem(itemId, quantity) { calls.push(`gain:${itemId}:${quantity}`); }
    };
    const npc = loadScript("gms-server/scripts/npc/9130000.js", { cm, Java });
    npc.start();
    if (options.selection !== undefined) {
        npc.action(1, 0, options.selection);
    }
    return { calls, messages };
}

function testDailyTicketChoice() {
    let result = runDailyNpc({ selection: 0 });
    assert.ok(result.messages[0].includes("4000697"));
    assert.ok(result.messages[0].includes("4000699"));
    assert.ok(result.calls.includes("complete"));
    assert.ok(result.calls.includes("gain:4000697:1"));
    assert.ok(!result.calls.includes("gain:4000699:1"));

    result = runDailyNpc({ selection: 1 });
    assert.ok(result.calls.includes("complete"));
    assert.ok(result.calls.includes("gain:4000699:1"));
    assert.ok(!result.calls.includes("gain:4000697:1"));

    result = runDailyNpc({ selection: 1, canHold: false });
    assert.ok(result.messages.some((message) => message.includes("空位")));
    assert.ok(!result.calls.includes("complete"));
    assert.ok(!result.calls.some((call) => call.startsWith("gain:")));
}

testLocalizedEventMirror();
testLocalizedDailyNpcMirror();
testEligibleParty();
testFinalStageTransition();
testNpcEntry();
testDailyTicketChoice();
console.log("Princess No entry contract checks passed");
