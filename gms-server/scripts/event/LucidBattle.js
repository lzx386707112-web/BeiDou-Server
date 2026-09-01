var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 220, maxLevel = 255;
var entryMap = 450004150;
var phaseTwoMap = 450004250;
var exitMap = 450004000;
var recruitMap = 450004000;
var eventTime = 30;
var maxDeaths = 50;

const maxLobbies = 1;
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
const LucidBossCompat = Java.type('org.gms.server.life.LucidBossCompat');
const PacketCreator = Java.type('org.gms.util.PacketCreator');
const AbstractAnimatedMapObject = Java.type('org.gms.server.maps.AbstractAnimatedMapObject');
const Point = Java.type('java.awt.Point');

var eventMaps = [entryMap, phaseTwoMap];

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function getEventMaps() {
    var ArrayList = Java.type('java.util.ArrayList');
    var maps = new ArrayList();
    for (var i = 0; i < eventMaps.length; i++) {
        maps.add(eventMaps[i]);
    }
    return maps;
}

function setEventRequirements() {
    em.setProperty("party", "\r\n   Players: 1 ~ 30\r\n   Level: 220 ~ 255\r\n   Time limit: 30 minutes\r\n   Death limit: 50 per character");
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
    var eim = em.newInstance("LucidBattle" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("phase", 1);
    for (var i = 0; i < eventMaps.length; i++) {
        var map = eim.getInstanceMap(eventMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    var phaseOneMap = eim.getInstanceMap(entryMap);
    var phaseOneBoss = LifeFactory.getMonster(8880140);
    phaseOneMap.spawnMonsterOnGroundBelow(phaseOneBoss, new Point(1000, 0));
    LucidBossCompat.startPhase(phaseOneMap, phaseOneBoss, 1);
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var id = player.getId();
    if (eim.getIntProperty("eliminated_" + id) == 1) {
        eim.unregisterPlayer(player);
        player.changeMap(exitMap, 0);
        player.dropMessage(5, "You have reached the 50-death limit for this Lucid expedition.");
        return;
    }
    if (eim.getIntProperty("joined_" + id) == 0) {
        for (var i = 0; i < eventMaps.length; i++) {
            player.resetEnteredScript(eventMaps[i]);
        }
        eim.setIntProperty("death_" + id, 0);
        eim.setIntProperty("joined_" + id, 1);
    }
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
    var mapId = player.getMapId();
    if (!isEventMap(mapId)) {
        return true;
    }
    var deathKey = "death_" + player.getId();
    var deaths = eim.getIntProperty(deathKey) + 1;
    eim.setIntProperty(deathKey, deaths);
    if (deaths >= maxDeaths) {
        eim.setIntProperty("eliminated_" + player.getId(), 1);
        player.dropMessage(5, "You have died 50 times and will return to the Nightmare Clocktower.");
        player.respawn(eim, exitMap);
        disposeIfEmpty(eim);
        return false;
    }

    player.cancelAllBuffs(false);
    player.updateHp(50);
    player.setStance(0);
    player.enableActions();
    var reviveMap = eim.getInstanceMap(mapId);
    reviveMap.movePlayer(player, reviveMap.getPortal(0).getPosition());
    var reviveMovement = PacketCreator.movePlayer(
        player.getId(), player.getIdleMovement(),
        AbstractAnimatedMapObject.IDLE_MOVEMENT_PACKET_LENGTH);
    player.sendPacket(reviveMovement);
    reviveMap.broadcastMessage(player, reviveMovement, false);
    player.dropMessage(5, "Lucid expedition deaths: " + deaths + "/" + maxDeaths);
    return false;
}

function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function playerUnregistered(eim, player) {}
function leftParty(eim, player) {}
function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return mobId == 8880140 || mobId == 8880141 || mobId == 8880142 ? 1 : 0;
}

function monsterKilled(mob, eim, hasKiller) {
    if (!hasKiller) {
        return;
    }
    if (mob.getId() == 8880140 && eim.getIntProperty("phase") == 1) {
        eim.setIntProperty("phase", 2);
        eim.dropMessage(5, "[Expedition] Lucid has escaped into the collapsing clocktower.");
        eim.schedule("advanceToPhaseTwo", 2500);
    } else if (mob.getId() == 8880142 && !eim.isEventCleared()) {
        clearPQ(eim);
    }
}

function advanceToPhaseTwo(eim) {
    var phaseOneMap = eim.getInstanceMap(entryMap);
    var targetMap = eim.getInstanceMap(phaseTwoMap);
    LucidBossCompat.stop(phaseOneMap);
    phaseOneMap.killAllMonsters();
    targetMap.killAllMonsters();
    var phaseTwoBoss = LifeFactory.getMonster(8880141);
    targetMap.spawnMonsterOnGroundBelow(phaseTwoBoss, new Point(600, -100));
    LucidBossCompat.startPhase(targetMap, phaseTwoBoss, 2);
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        players.get(i).changeMap(targetMap, targetMap.getPortal(0));
    }
}

function allMonstersDead(eim, hasKiller) {}
function monsterRevive(eim, mob) {
    if (mob.getId() == 8880142) {
        eim.setIntProperty("phase", 3);
        LucidBossCompat.startPhase(eim.getInstanceMap(phaseTwoMap), mob, 3);
    }
}

function clearPQ(eim) {
    stopLucidCompat(eim);
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    eim.dropMessage(5, "[Expedition] Lucid has been defeated. This map will remain open for 5 minutes.");
    eim.startEventTimer(300000);
}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    stopLucidCompat(eim);
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        playerExit(eim, players.get(i));
    }
    eim.dispose();
}

function disposeIfEmpty(eim) {
    if (eim.getPlayers().isEmpty()) {
        stopLucidCompat(eim);
        eim.dispose();
    }
}

function stopLucidCompat(eim) {
    for (var i = 0; i < eventMaps.length; i++) {
        LucidBossCompat.stop(eim.getInstanceMap(eventMaps[i]));
    }
}

function giveRandomEventReward(eim, player) {}
function cancelSchedule() {}
function dispose(eim) {}
