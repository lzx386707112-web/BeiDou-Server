var isPq = true;
var minPlayers = 1, maxPlayers = 6;
var minLevel = 140, maxLevel = 255;
var exitMap = 865000001;
var recruitMap = 865000001;
var stateAreaId = 32010;
var routeMaps = [865000100, 865000200, 865000300, 865000400, 865000501, 865000900];
var routeNames = ["多尔切", "露娜", "罗萨", "赫尔", "里恩", "北方海域"];
var routeMinutes = [3, 5, 7, 9, 11, 13];
var bossLoot = [4007000, 5570000, 1012438, 1022211, 1032224, 1122269, 1132247];
var routeWaves = [
    [{ mob: 9390800, count: 9 }, { mob: 9390806, count: 12 }, { mob: 9390803, count: 3, waterX: 320 }],
    [{ mob: 9390800, count: 12 }, { mob: 9390807, count: 12 }, { mob: 9390803, count: 3, waterX: 320 }],
    [{ mob: 9390806, count: 12 }, { mob: 9390807, count: 15 }, { mob: 9390803, count: 3, waterX: 320 }],
    [{ mob: 9390806, count: 15 }, { mob: 9390808, count: 15 }, { mob: 9390803, count: 3, waterX: 320 }, { mob: 9390804, count: 3, waterX: 350 }],
    [{ mob: 9390807, count: 15 }, { mob: 9390808, count: 15 }, { mob: 9390803, count: 3, waterX: 320 }, { mob: 9390806, count: 15 }, { mob: 9390804, count: 3, waterX: 350 }],
    [{ mob: 9390808, count: 15 }, { mob: 9390807, count: 15 }, { mob: 9390803, count: 3, waterX: 320 }, { mob: 9390806, count: 15 }, { mob: 9390804, count: 3, waterX: 350 }]
];
var spawnXs = [-300, -180, -60, 60, 180];
var waterSpawnOffsets = [-400, 0, 400];
var waterSurfaceSearchY = 400;
var maxLobbies = 8;
var LifeFactory = Java.type('org.gms.server.life.LifeFactory');
var Point = Java.type('java.awt.Point');
var Short = Java.type('java.lang.Short');

function init() {}
function getMaxLobbies() { return maxLobbies; }
function setEventRequirements() {}
function setEventExclusives(eim) { eim.setExclusiveItems([]); }
function setEventRewards(eim) { eim.setEventRewards(1, [], []); }

function getEligibleParty(party) {
    var eligible = [];
    var hasLeader = false;
    if (party.size() > 0) {
        var members = party.toArray();
        for (var i = 0; i < party.size(); i++) {
            var member = members[i];
            if (member.getMapId() == recruitMap
                    && member.getLevel() >= minLevel
                    && member.getLevel() <= maxLevel) {
                if (member.isLeader()) hasLeader = true;
                eligible.push(member);
            }
        }
    }
    if (!hasLeader || eligible.length < minPlayers || eligible.length > maxPlayers) eligible = [];
    return Java.to(eligible, Java.type("org.gms.net.server.world.PartyCharacter[]"));
}

function setup(difficulty, lobbyId) {
    var route = parseInt(difficulty) - 1;
    if (route < 0 || route >= routeMaps.length) route = 0;
    var eim = em.newInstance("CommerciVoyage" + lobbyId);
    eim.setIntProperty("route", route);
    eim.setIntProperty("wave", 0);
    eim.setIntProperty("waveCount", routeWaves[route].length);
    eim.setIntProperty("waveTransition", 0);
    eim.setIntProperty("finished", 0);
    eim.setIntProperty("bossDefeated", 0);
    var map = eim.getInstanceMap(routeMaps[route]);
    map.resetPQ(1);
    map.killAllMonsters();
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function spawnWaterMonster(map, monster, waveData, index) {
    var x = waveData.waterX + waterSpawnOffsets[index % waterSpawnOffsets.length];
    var searchPoint = new Point(x, waterSurfaceSearchY);
    var foothold = map.getFootholds().findBelow(searchPoint);
    if (foothold != null) monster.setFh(foothold.getId());
    map.spawnMonsterOnGroundBelow(monster, searchPoint);
}

function spawnWave(eim) {
    var route = eim.getIntProperty("route"), wave = eim.getIntProperty("wave");
    if (eim.isEventCleared() || eim.getIntProperty("finished") != 0 || wave >= routeWaves[route].length) return;
    var waveData = routeWaves[route][wave];
    var map = eim.getInstanceMap(routeMaps[route]);
    for (var i = 0; i < waveData.count; i++) {
        var monster = LifeFactory.getMonster(waveData.mob);
        if (waveData.waterX != null) {
            spawnWaterMonster(map, monster, waveData, i);
        } else {
            map.spawnMonsterOnGroundBelow(monster, new Point(spawnXs[i % spawnXs.length], 0));
        }
    }
    eim.setIntProperty("waveTransition", 0);
    eim.dropMessage(5, "[航海] " + routeNames[route] + "第 " + (wave + 1) + "/" + routeWaves[route].length + " 波开始，共 " + waveData.count + " 只怪物。");
}

function afterSetup(eim) {
    spawnWave(eim);
    eim.startEventTimer(routeMinutes[eim.getIntProperty("route")] * 60000);
}
function playerEntry(eim, player) { player.changeMap(eim.getMapInstance(routeMaps[eim.getIntProperty("route")]), 0); }
function scheduledTimeout(eim) { completeVoyage(eim, false); }
function changedMap(eim, player, mapid) {
    if (mapid != routeMaps[eim.getIntProperty("route")]) {
        eim.unregisterPlayer(player);
        if (eim.getPlayerCount() < 1) end(eim);
    }
}
function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) {}
function playerDisconnected(eim, player) { eim.unregisterPlayer(player); if (eim.getPlayerCount() < 1) end(eim); }
function leftParty(eim, player) {}
function disbandParty(eim) { end(eim); }
function monsterValue(eim, mobId) { return 1; }
function playerUnregistered(eim, player) {}
function playerExit(eim, player) { eim.unregisterPlayer(player); player.changeMap(exitMap, 0); }

function monsterKilled(mob, eim) {
    var route = eim.getIntProperty("route"), map = eim.getInstanceMap(routeMaps[route]);
    if (mob.getId() == 9390803 || mob.getId() == 9390804) eim.setIntProperty("bossDefeated", 1);
    if (map.countMonsters() > 0 || eim.getIntProperty("waveTransition") != 0 || eim.getIntProperty("finished") != 0) return;
    eim.setIntProperty("waveTransition", 1);
    var wave = eim.getIntProperty("wave") + 1;
    if (wave < routeWaves[route].length) {
        eim.setIntProperty("wave", wave);
        eim.dropMessage(5, "[航海] 本波已清除，下一波将在 2 秒后开始。");
        eim.schedule("spawnWave", 2000);
        return;
    }
    completeVoyage(eim, true);
}

function stateKey() { return Short.valueOf(String(stateAreaId)); }

function intValue(value, fallback) {
    var parsed = parseInt(value);
    return isNaN(parsed) ? fallback : parsed;
}

function parseState(raw) {
    if (raw == null) return null;
    var p = String(raw).split("|");
    if (p.length < 21 || p[0] != "C1") return null;
    return {
        parts: p,
        counts: String(p[9]).split(","),
        cargoCap: Math.max(2, intValue(p[7], 2)),
        cargo: String(p[11]).split(","),
        pendingCoins: Math.max(0, intValue(p[12], 0)),
        pendingExp: Math.max(0, intValue(p[13], 0)),
        pendingItem: Math.max(0, intValue(p[14], 0)),
        pendingItemQty: Math.max(0, intValue(p[15], 0)),
        active: intValue(p[16], 0),
        activeRoute: intValue(p[17], -1),
        activeReward: Math.max(0, intValue(p[18], 0)),
        activeExp: Math.max(0, intValue(p[19], 0))
    };
}

function saveCompletedVoyage(player, route, rewardPercent, bossDefeated) {
    var key = stateKey();
    var state = parseState(player.getAreaInfos().get(key));
    if (state == null || state.active != 1 || state.activeRoute != route) return;
    var reward = Math.max(1, Math.floor(state.activeReward * rewardPercent / 100));
    if (bossDefeated && Math.random() < 0.25) reward += 5 + Math.floor(Math.random() * 11);
    state.pendingCoins += reward;
    state.pendingExp += state.activeExp;
    state.counts[route] = intValue(state.counts[route], 0) + 1;
    if (bossDefeated && route >= 3 && state.pendingItem == 0 && Math.random() < 0.10) {
        state.pendingItem = bossLoot[Math.floor(Math.random() * bossLoot.length)];
        state.pendingItemQty = 1;
    }
    var cargoUsed = 0;
    for (var i = 0; i < state.cargo.length; i++) cargoUsed += intValue(state.cargo[i], 0);
    if (bossDefeated && cargoUsed < state.cargoCap && Math.random() < 0.15) {
        var rareGood = Math.random() < 0.5 ? 4 : 5;
        state.cargo[rareGood] = intValue(state.cargo[rareGood], 0) + 1;
    }
    state.parts[9] = state.counts.join(",");
    state.parts[11] = state.cargo.join(",");
    state.parts[12] = String(state.pendingCoins);
    state.parts[13] = String(state.pendingExp);
    state.parts[14] = String(state.pendingItem);
    state.parts[15] = String(state.pendingItemQty);
    state.parts[16] = "0";
    state.parts[17] = "-1";
    state.parts[18] = "0";
    state.parts[19] = "0";
    state.parts[20] = "0";
    player.getAreaInfos().put(key, state.parts.join("|"));
}

function completeVoyage(eim, clearedAllWaves) {
    if (eim.getIntProperty("finished") != 0) return;
    eim.setIntProperty("finished", 1);
    var route = eim.getIntProperty("route");
    var rewardPercent = 100;
    if (!clearedAllWaves) {
        var remaining = routeWaves[route].length - eim.getIntProperty("wave");
        rewardPercent = Math.max(50, 100 - remaining * 10);
    }
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        saveCompletedVoyage(players.get(i), route, rewardPercent, eim.getIntProperty("bossDefeated") != 0);
    }
    if (clearedAllWaves) {
        eim.dropMessage(5, "[航海] 所有威胁已清除，提前到港。请回交易所向仔北卢领取收益。");
        eim.stopEventTimer();
    } else {
        eim.dropMessage(5, "[航海] 已到达目的地，未清除的威胁造成了 " + (100 - rewardPercent) + "% 货损。请向仔北卢领取收益。");
    }
    eim.schedule("finishVoyage", 3000);
    eim.setEventCleared();
}

function finishVoyage(eim) { end(eim); }

function end(eim) {
    var players = eim.getPlayers();
    for (var i = players.size() - 1; i >= 0; i--) playerExit(eim, players.get(i));
    eim.dispose();
}
function clearPQ(eim) { eim.setEventCleared(); }
function allMonstersDead(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
