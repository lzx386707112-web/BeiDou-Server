/**
 * Monster Park instance. Course start map is selected by NPC 9071000.
 */

var isPq = true;
var minPlayers = 1;
var maxPlayers = 6;
var minLevel = 105;
var maxLevel = 250;
var exitMap = 951000000;
var recruitMap = 951000000;
var eventTime = 10;
var maxLobbies = 8;

function init() {
    em.setProperty("party", "\r\n    人数: 1 ~ 6\r\n    等级: 105+\r\n    时限: 10 分钟");
}

function getMaxLobbies() {
    return maxLobbies;
}

function getEligibleParty(party) {
    var eligible = [];
    var hasLeader = false;
    if (party.size() > 0) {
        var partyList = party.toArray();
        for (var i = 0; i < party.size(); i++) {
            var ch = partyList[i];
            if (ch.getMapId() == recruitMap && ch.getLevel() >= minLevel) {
                if (ch.isLeader()) {
                    hasLeader = true;
                }
                eligible.push(ch);
            }
        }
    }
    if (!(hasLeader && eligible.length >= minPlayers && eligible.length <= maxPlayers)) {
        eligible = [];
    }
    return Java.to(eligible, Java.type("org.gms.net.server.world.PartyCharacter[]"));
}

function setup(level, lobbyid) {
    var start = parseInt(em.getProperty("course"));
    var eim = em.newInstance("MonsterPark" + lobbyid);
    eim.setProperty("course", String(start));
    eim.setProperty("parkRegion", em.getProperty("parkRegion") || "");
    eim.setProperty("level", level);
    for (var i = 0; i < 6; i++) {
        eim.getInstanceMap(start + (i * 100)).resetPQ(level);
    }
    eim.startEventTimer(eventTime * 60000);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var map = eim.getMapInstance(parseInt(eim.getProperty("course")));
    player.changeMap(map, map.getPortal(0));
    player.dropMessage(5, "消灭本图所有怪物后，走上方传送门进入下一关。点休菲凯曼可以离开。");
}

function scheduledTimeout(eim) {
    end(eim);
}

function playerUnregistered(eim, player) {}

function playerExit(eim, player) {
    eim.unregisterPlayer(player);
    player.changeMap(exitMap, 0);
}

function playerLeft(eim, player) {
    if (!eim.isEventCleared()) {
        playerExit(eim, player);
    }
}

function inCourse(eim, mapid) {
    var start = parseInt(eim.getProperty("course"));
    return mapid >= start && mapid <= start + 500 && (mapid - start) % 100 == 0;
}

function changedMap(eim, player, mapid) {
    if (!inCourse(eim, mapid) && mapid != exitMap) {
        if (eim.isEventTeamLackingNow(true, minPlayers, player)) {
            eim.unregisterPlayer(player);
            end(eim);
        } else {
            eim.unregisterPlayer(player);
        }
    }
}

function changedLeader(eim, leader) {}

function playerDead(eim, player) {}

function playerRevive(eim, player) {
    playerExit(eim, player);
}

function playerDisconnected(eim, player) {
    if (eim.isEventTeamLackingNow(true, minPlayers, player)) {
        eim.unregisterPlayer(player);
        end(eim);
    } else {
        eim.unregisterPlayer(player);
    }
}

function leftParty(eim, player) {
    if (eim.isEventTeamLackingNow(false, minPlayers, player)) {
        end(eim);
    } else {
        playerLeft(eim, player);
    }
}

function disbandParty(eim) {
    if (!eim.isEventCleared()) {
        end(eim);
    }
}

function monsterValue(eim, mobId) {
    return 1;
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

function monsterKilled(mob, eim) {}

function allMonstersDead(eim) {
    eim.dropMessage(5, "怪物已清空，请走上方传送门进入下一阶段。");
}

function cancelSchedule() {}

function dispose(eim) {}
