/*
    Chaos Zakum Battle
*/

var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 120, maxLevel = 255;
var entryMap = 280030001;
var exitMap = 211042401;
var recruitMap = 211042401;
var clearMap = 211042401;

var minMapId = 280030001;
var maxMapId = 280030001;

var eventTime = 75;

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
    var eim = em.newInstance("ChaosZakum" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);
    eim.setProperty("summoned", "false");

    eim.getInstanceMap(entryMap).resetPQ(1);

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

function isChaosZakum(mob) {
    return mob.getId() == 8800102;
}

function monsterKilled(mob, eim) {
    if (isChaosZakum(mob)) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        eim.clearPQ();
        mob.getMap().broadcastZakumVictory();
    }
}

function allMonstersDead(eim) {}

function cancelSchedule() {}

function dispose(eim) {}
