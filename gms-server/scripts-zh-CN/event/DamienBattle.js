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
    phaseOneMap.spawnMonsterOnGroundBelow(LifeFactory.getMonster(phaseOneBoss), new Point(spawnX, spawnY));
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

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
    if (!hasKiller) {
        return;
    }
    if (mob.getId() == phaseOneBoss && eim.getIntProperty("phase") == 1) {
        eim.setIntProperty("phase", 2);
        eim.schedule("advanceToPhaseTwo", 2500);
    } else if (mob.getId() == phaseTwoBoss && !eim.isEventCleared()) {
        eim.setProperty("canJoin", "0");
        eim.schedule("clearPQ", 1000);
    }
}

function advanceToPhaseTwo(eim) {
    var targetMap = eim.getInstanceMap(phaseTwoMap);
    eim.getInstanceMap(entryMap).killAllMonsters();
    targetMap.killAllMonsters();
    targetMap.spawnMonsterOnGroundBelow(LifeFactory.getMonster(phaseTwoBoss), new Point(spawnX, spawnY));
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        players.get(i).changeMap(targetMap, targetMap.getPortal(0));
    }
}

function allMonstersDead(eim, hasKiller) {}
function monsterRevive(eim, mob) {}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    eim.startEventTimer(300000);
}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        playerExit(eim, players.get(i));
    }
    eim.dispose();
}

function disposeIfEmpty(eim) {
    if (eim.getPlayers().isEmpty()) {
        eim.dispose();
    }
}

function giveRandomEventReward(eim, player) {}
function cancelSchedule() {}
function dispose(eim) {}
