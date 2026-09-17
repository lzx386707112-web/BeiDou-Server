/**
 * 戴米安副本：两阶段只刷怪。DamienBossCompat 仅 skill2 光球，换图时 stop。
 */
var minPlayers = 1, maxPlayers = 30;
var minLevel = 180, maxLevel = 255;
var entryMap = 350160240;
var phaseTwoMap = 350160280;
var exitMap = 105300303;
var eventTime = 30;
var eventMaps = [entryMap, phaseTwoMap];
var phaseOneBoss = 8880110;
var phaseTwoBoss = 8880111;
var spawnX = 800;
var spawnY = 17;
const maxLobbies = 1;
const LifeFactory = Java.type("org.gms.server.life.LifeFactory");
const DamienBossCompat = Java.type("org.gms.server.life.DamienBossCompat");
const Point = Java.type("java.awt.Point");

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function getEventMaps() {
    var ArrayList = Java.type("java.util.ArrayList");
    var maps = new ArrayList();
    for (var i = 0; i < eventMaps.length; i++) {
        maps.add(eventMaps[i]);
    }
    return maps;
}

function setEventRequirements() {
    em.setProperty("party", "\r\n   组队人数: 1 ~ 30\r\n   等级要求: 180 ~ 255\r\n   时间限制: 30 分钟");
}

function setEventExclusives(eim) {
    eim.setExclusiveItems([]);
}

function setEventRewards(eim) {
    eim.setEventRewards(1, [], []);
    eim.setEventClearStageExp([]);
    eim.setEventClearStageMeso([]);
}

function setup(channel) {
    var eim = em.newInstance("DAMIEN" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("phase", 1);
    for (var i = 0; i < eventMaps.length; i++) {
        var map = eim.getInstanceMap(eventMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    var phaseOneMap = eim.getInstanceMap(entryMap);
    var boss = LifeFactory.getMonster(phaseOneBoss);
    phaseOneMap.spawnMonsterOnGroundBelow(boss, new Point(spawnX, spawnY));
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

// 一阶段与希纳斯相同：地上刷怪后不挂 Encounter。
function afterSetup(eim) {}

function playerEntry(eim, player) {
    var targetMapId = eim.getIntProperty("phase") >= 2 ? phaseTwoMap : entryMap;
    var map = eim.getInstanceMap(targetMapId);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function isEventMap(mapId) {
    return mapId == entryMap || mapId == phaseTwoMap;
}

function changedMap(eim, player, mapId) {
    if (isEventMap(mapId)) {
        return;
    }
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) {
    return true;
}

function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function playerUnregistered(eim, player) {}
function leftParty(eim, player) {}
function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return mobId == phaseOneBoss || mobId == phaseTwoBoss ? 1 : 0;
}

function monsterKilled(mob, eim, hasKiller) {
    if (mob.getId() == phaseOneBoss && eim.getIntProperty("phase") == 1) {
        eim.setIntProperty("phase", 2);
        eim.schedule("advanceToPhaseTwo", 2500);
    } else if (mob.getId() == phaseTwoBoss && !eim.isEventCleared()) {
        eim.setProperty("canJoin", "0");
        eim.schedule("clearPQ", 1000);
    }
}

function advanceToPhaseTwo(eim) {
    var fromMap = eim.getInstanceMap(entryMap);
    var targetMap = eim.getInstanceMap(phaseTwoMap);
    DamienBossCompat.stop(fromMap);
    fromMap.killAllMonsters();
    targetMap.killAllMonsters();
    var phaseTwo = LifeFactory.getMonster(phaseTwoBoss);
    targetMap.spawnMonsterOnGroundBelow(phaseTwo, new Point(spawnX, spawnY));
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        players.get(i).changeMap(targetMap, targetMap.getPortal(0));
    }
    // 进图后再刷场地怪：单独召唤不崩、进图崩时用来区分地图资源和 8880113/8880114。
    DamienBossCompat.startPhase(targetMap, phaseTwo, 2);
}

function allMonstersDead(eim, hasKiller) {}
function monsterRevive(eim, mob) {}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    DamienBossCompat.stop(eim.getInstanceMap(entryMap));
    DamienBossCompat.stop(eim.getInstanceMap(phaseTwoMap));
    eim.startEventTimer(300000);
}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    DamienBossCompat.stop(eim.getInstanceMap(entryMap));
    DamienBossCompat.stop(eim.getInstanceMap(phaseTwoMap));
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        playerExit(eim, players.get(i));
    }
    eim.dispose();
}

function disposeIfEmpty(eim) {
    if (eim.getPlayers().isEmpty()) {
        DamienBossCompat.stop(eim.getInstanceMap(entryMap));
        DamienBossCompat.stop(eim.getInstanceMap(phaseTwoMap));
        eim.dispose();
    }
}

function giveRandomEventReward(eim, player) {}
function cancelSchedule() {}
function dispose(eim) {
    DamienBossCompat.stop(eim.getInstanceMap(entryMap));
    DamienBossCompat.stop(eim.getInstanceMap(phaseTwoMap));
}
