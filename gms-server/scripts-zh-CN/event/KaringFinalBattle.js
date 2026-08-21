var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 100, maxLevel = 255;
var entryMap = 410007100;
var exitMap = 910000000;
var recruitMap = 910000000;
var eventTime = 120;
var maxDeaths = 20;

const maxLobbies = 1;
const Point = Java.type('java.awt.Point');

var eventMaps = [
    410007100, 410007120, 410007140, 410007160,
    410007180, 410007200, 410007220, 410007240,
    410007260, 410007280, 410007300
];
var battleMaps = {
    "410007140": [-441, 107],
    "410007180": [-441, 107],
    "410007220": [-413, 107],
    "410007260": [-270, 107],
    "410007300": [-1853, 399]
};

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
    em.setProperty("party", "\r\n   组队人数：1 ~ 30\r\n   等级要求：100 ~ 255\r\n   时间限制：120 分钟\r\n   死亡限制：每个角色 20 次");
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
    var eim = em.newInstance("KaringFinalBattle" + channel);
    eim.setProperty("canJoin", "1");
    for (var i = 0; i < eventMaps.length; i++) {
        var map = eim.getInstanceMap(eventMaps[i]);
        map.resetPQ(1);
        map.killAllMonsters();
    }
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

function afterSetup(eim) {}

function playerEntry(eim, player) {
    var id = player.getId();
    var eliminatedKey = "eliminated_" + id;
    if (eim.getIntProperty(eliminatedKey) == 1) {
        eim.unregisterPlayer(player);
        player.changeMap(exitMap, 0);
        player.dropMessage(5, "你在本次咖凌远征中已达到 20 次死亡上限。");
        return;
    }

    var joinedKey = "joined_" + id;
    var lastMapKey = "last_map_" + id;
    if (eim.getIntProperty(joinedKey) == 0) {
        for (var i = 0; i < eventMaps.length; i++) {
            player.resetEnteredScript(eventMaps[i]);
        }
        eim.setIntProperty("death_" + id, 0);
        eim.setIntProperty(joinedKey, 1);
        eim.setIntProperty(lastMapKey, entryMap);
    }

    var targetMapId = eim.getIntProperty(lastMapKey);
    if (!isEventMap(targetMapId)) {
        targetMapId = entryMap;
    }
    var map = eim.getMapInstance(targetMapId);
    player.changeMap(map, map.getPortal(0));
}

function scheduledTimeout(eim) {
    end(eim);
}

function isEventMap(mapId) {
    for (var i = 0; i < eventMaps.length; i++) {
        if (eventMaps[i] == mapId) {
            return true;
        }
    }
    return false;
}

function changedMap(eim, player, mapId) {
    if (isEventMap(mapId)) {
        eim.setIntProperty("last_map_" + player.getId(), mapId);
        return;
    }
    eim.unregisterPlayer(player);
    disposeIfEmpty(eim);
}

function changedLeader(eim, leader) {}
function playerDead(eim, player) {}

function playerRevive(eim, player) {
    var mapId = player.getMapId();
    var revivePoint = battleMaps[String(mapId)];
    // 进入动画/阶段过渡地图也可能弹出死亡确认；只有离开卡凌副本地图
    // 才交回通用 returnMap 处理，副本内始终使用 20 次复活规则。
    if (revivePoint == null && !isEventMap(mapId)) {
        return true;
    }

    var deathKey = "death_" + player.getId();
    var deaths = eim.getIntProperty(deathKey) + 1;
    eim.setIntProperty(deathKey, deaths);
    if (deaths >= maxDeaths) {
        eim.setIntProperty("eliminated_" + player.getId(), 1);
        player.dropMessage(5, "你已死亡 20 次，将返回自由市场。");
        player.respawn(eim, exitMap);
        disposeIfEmpty(eim);
        return false;
    }

    player.cancelAllBuffs(false);
    player.updateHp(50);
    player.setStance(0);
    var revivePosition = revivePoint == null
        ? player.getPosition()
        : new Point(revivePoint[0], revivePoint[1]);
    player.changeMap(eim.getMapInstance(mapId), revivePosition);
    player.dropMessage(5, "本次咖凌远征死亡次数：" + deaths + "/" + maxDeaths);
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
    return mobId == 8880830 || mobId == 8880831 || mobId == 8880832
        || mobId == 8880837 || mobId == 8880842 ? 1 : 0;
}

function monsterKilled(mob, eim, hasKiller) {
    if (mob.getId() == 8880842 && !eim.isEventCleared()) {
        clearPQ(eim);
    }
}

function allMonstersDead(eim, hasKiller) {}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setProperty("canJoin", "0");
    eim.setEventCleared();
    eim.dropMessage(5, "[远征队] 咖凌已被击败，当前地图将保留 5 分钟。");
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
