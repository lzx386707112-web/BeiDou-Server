var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 120, maxLevel = 255;
var entryMap = 807300110;
var exitMap = 807300100;
var recruitMap = 807300100;
var eventTime = 30;
var bossId = 9421581;
const maxLobbies = 1;
const GameConfig = Java.type('org.gms.config.GameConfig');
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
const Point = Java.type('java.awt.Point');

minPlayers = GameConfig.getServerBoolean("use_enable_solo_expeditions") ? 1 : minPlayers;
if (GameConfig.getServerBoolean("use_enable_party_level_limit_lift")) {
    minLevel = 1;
}

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    em.setProperty("party", "\r\n   组队人数：1 ~ 30\r\n   等级要求：120+\r\n   时间限制：30 分钟");
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
    var eim = em.newInstance("RanmaruBattle" + channel);
    eim.setProperty("canJoin", "1");
    eim.setIntProperty("defeatedBoss", 0);
    var map = eim.getInstanceMap(entryMap);
    map.resetPQ(1);
    map.killAllMonsters();
    var mob = LifeFactory.getMonster(bossId);
    map.spawnMonsterOnGroundBelow(mob, new Point(200, 100));
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
    if (mapid != entryMap) {
        eim.unregisterPlayer(player);
        if (eim.getPlayerCount() < 1) {
            end(eim);
        }
    }
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}
function playerRevive(eim, player) {}
function playerDisconnected(eim, player) {
    eim.unregisterPlayer(player);
    if (eim.getPlayerCount() < 1) {
        end(eim);
    }
}
function leftParty(eim, player) {}
function disbandParty(eim) {}
function monsterValue(eim, mobId) { return 1; }
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

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setEventCleared();
    eim.setProperty("canJoin", "0");
    eim.dropMessage(5, "[远征队] 森兰丸已被击败。");
    eim.startEventTimer(60000);
}

function monsterKilled(mob, eim) {
    if (mob.getId() == bossId && eim.getIntProperty("defeatedBoss") == 0) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        clearPQ(eim);
    }
}

function allMonstersDead(eim) {}
function cancelSchedule() {}
function dispose(eim) {}
