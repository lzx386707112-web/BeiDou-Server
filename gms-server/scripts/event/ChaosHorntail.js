/*
    Chaos Horntail Battle
*/

var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 120, maxLevel = 255;
var entryMap = 240060001;
var exitMap = 240050400;
var recruitMap = 240050400;
var clearMap = 240050400;

var minMapId = 240060001;
var maxMapId = 240060201;

var eventTime = 120;

const maxLobbies = 1;

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    var reqStr = "";

    reqStr += "\r\n    Number of players: ";
    reqStr += (maxPlayers - minPlayers >= 1) ? minPlayers + " ~ " + maxPlayers : minPlayers;

    reqStr += "\r\n    Level range: ";
    reqStr += (maxLevel - minLevel >= 1) ? minLevel + " ~ " + maxLevel : minLevel;

    reqStr += "\r\n    Time limit: ";
    reqStr += eventTime + " minutes";

    em.setProperty("party", reqStr);
}

function setEventExclusives(eim) {
    eim.setExclusiveItems([]);
}

function setEventRewards(eim) {
    eim.setEventRewards(1, [], []);
    eim.setEventClearStageExp([]);
    eim.setEventClearStageMeso([]);
}

function afterSetup(eim) {}

function setup(channel) {
    var eim = em.newInstance("ChaosHorntail" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);
    eim.setProperty("defeatedHead", 0);

    var level = 1;
    eim.getInstanceMap(240060001).resetPQ(level);
    eim.getInstanceMap(240060101).resetPQ(level);
    eim.getInstanceMap(240060201).resetPQ(level);

    const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
    const Point = Java.type('java.awt.Point');
    var map, mob;
    map = eim.getInstanceMap(240060001);
    mob = LifeFactory.getMonster(8810128);
    map.spawnMonsterOnGroundBelow(mob, new Point(890, 230));

    map = eim.getInstanceMap(240060101);
    mob = LifeFactory.getMonster(8810129);
    map.spawnMonsterOnGroundBelow(mob, new Point(-360, 230));

    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);

    return eim;
}

function playerEntry(eim, player) {
    eim.dropMessage(5, "[Expedition] " + player.getName() + " has entered the map.");
    var map = eim.getMapInstance(entryMap);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function changedMap(eim, player, mapid) {
    if (mapid < minMapId || mapid > maxMapId) {
        if (eim.isExpeditionTeamLackingNow(true, minPlayers, player)) {
            eim.unregisterPlayer(player);
            eim.dropMessage(5, "[Expedition] Either the leader has quit the expedition or there is no longer the minimum number of members required to continue it.");
            end(eim);
        } else {
            eim.dropMessage(5, "[Expedition] " + player.getName() + " has left the instance.");
            eim.unregisterPlayer(player);
        }
    }
}

function changedLeader(eim, leader) {}

function playerDead(eim, player) {}

function playerRevive(eim, player) {
    changedMap(eim, player, exitMap);
}

function playerDisconnected(eim, player) {
    changedMap(eim, player, exitMap);
}

function leftParty(eim, player) {}

function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return 1;
}

function playerUnregistered(eim, player) {}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function end(eim) {
    var party = eim.getPlayers();
    for (var i = 0; i < party.size(); i++) {
        playerExit(eim, party.get(i));
    }
    eim.dispose();
}

function giveRandomEventReward(eim, player) {
    eim.giveEventReward(player);
}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setEventCleared();
}

function isChaosHorntailHead(mob) {
    var mobid = mob.getId();
    return (mobid == 8810100 || mobid == 8810101);
}

function isChaosHorntail(mob) {
    return mob.getId() == 8810018;
}

function monsterKilled(mob, eim) {
    if (isChaosHorntail(mob)) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        eim.clearPQ();

        mob.getMap().broadcastHorntailVictory();
    } else if (isChaosHorntailHead(mob)) {
        var killed = eim.getIntProperty("defeatedHead");
        eim.setIntProperty("defeatedHead", killed + 1);
        eim.showClearEffect(mob.getMap().getId());
    }
}

function allMonstersDead(eim) {}

function cancelSchedule() {}

function dispose(eim) {}
