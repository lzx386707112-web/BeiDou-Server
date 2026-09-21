var isPq = true;
var minPlayers = 1, maxPlayers = 6;
var minLevel = 160, maxLevel = 255;
var eventTime = 30;
var entryMap = 811000100;
var exitMap = 807000000;
var recruitMap = 811000999;
var stageMaps = [811000100, 811000200, 811000300, 811000400, 811000500];
var stageMobs = [9450035, 9450037, 9450038, 9450039, 9450040];
var stageSpawns = [[0, 0], [0, 0], [0, 0], [0, 0], [0, -235]];
var maxLobbies = 1;
var LifeFactory = Java.type('org.gms.server.life.LifeFactory');
var Point = Java.type('java.awt.Point');

function init() { setEventRequirements(); }
function getMaxLobbies() { return maxLobbies; }
function setEventRequirements() {
    em.setProperty("party", "\r\n   组队人数：1 ~ 6\r\n   等级要求：160+\r\n   时间限制：30 分钟");
}
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

function setup(channel) {
    var eim = em.newInstance("PrincessNoBattle" + channel);
    eim.setIntProperty("stage", 0);
    for (var i = 0; i < stageMaps.length; i++) {
        var map = eim.getInstanceMap(stageMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    spawnStage(eim, 0);
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function spawnStage(eim, stage) {
    var map = eim.getInstanceMap(stageMaps[stage]);
    var spawn = stageSpawns[stage];
    map.spawnMonsterOnGroundBelow(
        LifeFactory.getMonster(stageMobs[stage]), new Point(spawn[0], spawn[1])
    );
}

function afterSetup(eim) {}
function playerEntry(eim, player) { player.changeMap(eim.getMapInstance(entryMap), 0); }
function scheduledTimeout(eim) { end(eim); }
function changedMap(eim, player, mapid) {
    if (stageMaps.indexOf(mapid) < 0) {
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
    var stage = eim.getIntProperty("stage");
    if (mob.getId() != stageMobs[stage]) return;
    if (stage == stageMaps.length - 1) {
        eim.showClearEffect(stageMaps[stage]);
        eim.setEventCleared();
        eim.startEventTimer(60000);
        return;
    }
    stage++;
    eim.setIntProperty("stage", stage);
    spawnStage(eim, stage);
    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) players.get(i).changeMap(eim.getMapInstance(stageMaps[stage]), 0);
}

function end(eim) {
    var players = eim.getPlayers();
    for (var i = players.size() - 1; i >= 0; i--) playerExit(eim, players.get(i));
    eim.dispose();
}
function clearPQ(eim) { eim.setEventCleared(); }
function allMonstersDead(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
