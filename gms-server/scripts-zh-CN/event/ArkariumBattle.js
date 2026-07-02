/*
    Cut-down Arkarium battle.
*/

var isPq = true;
var minPlayers = 1, maxPlayers = 6;
var minLevel = 1, maxLevel = 255;
var entryMap = 272020200;
var exitMap = 272020110;
var recruitMap = 272020110;
var clearMap = 272020110;

var minMapId = 272020200;
var maxMapId = 272020200;

var eventTime = 30;
const maxLobbies = 1;

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    em.setProperty("party", "\r\n    Number of players: 1 ~ 6\r\n    Level range: 1 ~ 255\r\n    Time limit: 30 minutes");
}

function setEventExclusives(eim) {
    eim.setExclusiveItems([]);
}

function setEventRewards(eim) {
    eim.setEventRewards(1, [], []);
    eim.setEventClearStageExp([]);
    eim.setEventClearStageMeso([]);
}

function setup(level, lobbyid) {
    var eim = em.newInstance("ArkariumBattle" + lobbyid);
    eim.setProperty("summoned", "0");
    eim.setProperty("defeatedBoss", "0");
    eim.getInstanceMap(entryMap).resetPQ(level);
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var map = eim.getMapInstance(entryMap);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function changedMap(eim, player, mapid) {
    if (mapid < minMapId || mapid > maxMapId) {
        eim.unregisterPlayer(player);
        if (eim.getPlayers().isEmpty()) {
            end(eim);
        }
    }
}

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

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setEventCleared();
}

function monsterValue(eim, mobId) {
    return mobId == 8860000 ? 1 : 0;
}

function monsterKilled(mob, eim) {
    if (mob.getId() == 8860000) {
        eim.setProperty("defeatedBoss", "1");
        eim.showClearEffect(mob.getMap().getId());
        eim.clearPQ();
        eim.dispatchRaiseQuestMobCount(8860000, entryMap);
    }
}

function playerUnregistered(eim, player) {}
function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) { playerExit(eim, player); }
function playerDisconnected(eim, player) { changedMap(eim, player, exitMap); }
function leftParty(eim, player) {}
function disbandParty(eim) {}
function giveRandomEventReward(eim, player) {}
function allMonstersDead(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
