/**
 * @author: Ronan
 * @event: CQ Battle
 * @optimized: 北斗GMS083 适配优化
 */

var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 125, maxLevel = 255;
var entryMap = 105200710;
var entryItem = 4033611;    // 入场消耗道具
var exitMap = 105200000;
var recruitMap = 105200000;
var clearMap = 105200000;

var minMapId = 105200710;
var maxMapId = 105200710;

var eventTime = 120;     // 120 minutes

const maxLobbies = 1;

const GameConfig = Java.type('org.gms.config.GameConfig');
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');

minPlayers = GameConfig.getServerBoolean("use_enable_solo_expeditions") ? 1 : minPlayers;
if (GameConfig.getServerBoolean("use_enable_party_level_limit_lift")) {
    minLevel = 125, maxLevel = 200;
}

var bossId = 8920000;         // 血腥女王 BOSS
var treasureMobId = 8920006;  // 宝箱怪物

function init() {
    setEventRequirements();
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    var reqStr = "";

    reqStr += "\r\n   组队人数: ";
    if (maxPlayers - minPlayers >= 1) {
        reqStr += minPlayers + " ~ " + maxPlayers;
    } else {
        reqStr += minPlayers;
    }

    reqStr += "\r\n   等级要求: ";
    if (maxLevel - minLevel >= 1) {
        reqStr += minLevel + " ~ " + maxLevel;
    } else {
        reqStr += minLevel;
    }

    reqStr += "\r\n   时间限制: ";
    reqStr += eventTime + " 分钟";

    em.setProperty("party", reqStr);
}

function setEventExclusives(eim) {
    var itemSet = [];
    eim.setExclusiveItems(itemSet);
}

function setEventRewards(eim) {
    var itemSet, itemQty, evLevel, expStages, mesoStages;

    evLevel = 1;    // 战后奖励，卷轴提升成功卡随机一种
    itemSet = [5610000, 5610001];
    itemQty = [1, 1];
    eim.setEventRewards(evLevel, itemSet, itemQty);

    expStages = [];    // bonus exp given on CLEAR stage signal
    eim.setEventClearStageExp(expStages);

    mesoStages = [];    // bonus meso given on CLEAR stage signal
    eim.setEventClearStageMeso(mesoStages);
}

function afterSetup(eim) {
    updateGateState(1);
}

function setup(channel) {
    var eim = em.newInstance("CQ" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);
    eim.setProperty("treasureSpawned", 0);
    var level = 1;
    var battleMap = eim.getInstanceMap(entryMap);
    battleMap.resetPQ(level);
    battleMap.killAllMonsters();

    // 自动召唤 血腥女王 BOSS
    var mob = LifeFactory.getMonster(bossId);
    battleMap.spawnMonsterOnGroundBelow(mob, new java.awt.Point(60, 134));
	
    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);

    return eim;
}

function playerEntry(eim, player) {
    eim.dropMessage(5, "[远征队] " + player.getName() + " 已进入副本地图。");

    var map = eim.getMapInstance(entryMap);

    player.changeMap(map, map.getPortal(0));


    // 扣除入场道具
    player.getAbstractPlayerInteraction().gainItem(entryItem, -0);
    //player.dropMessage(6, "消耗了入场道具 古树钥匙。");
}

function scheduledTimeout(eim) {
    end(eim);
}

function changedMap(eim, player, mapid) {
    if (mapid < minMapId || mapid > maxMapId) {
        partyPlayersCheck(eim, player);
    }
}

function changedLeader(eim, leader) {}

function playerDead(eim, player) {}

function playerRevive(eim, player) {
    partyPlayersCheck(eim, player);
}

function playerDisconnected(eim, player) {
    partyPlayersCheck(eim, player);
}

function leftParty(eim, player) {}

function disbandParty(eim) {}

function monsterValue(eim, mobId) {
    return 1;
}

function playerUnregistered(eim, player) {
    if (eim.isEventCleared()) {
        em.completeQuest(player, 100200, 2030010);
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

function giveRandomEventReward(eim, player) {
    eim.giveEventReward(player);
}

function clearPQ(eim) {
    eim.stopEventTimer();
    eim.setEventCleared();
    eim.setProperty("canJoin", 0);  // 禁止后续玩家进入
    eim.dropMessage(5, "[远征队] 恭喜！你们成功击败了 血腥女王！");
    updateGateState(0);
    eim.startEventTimer(300000); // 通关后5分钟强制清场，注意此时无法重连
}

function isQueen(mob) {
    return mob.getId() >= 8920000 && mob.getId() <= 8920002;
}

function hasAliveQueen(map) {
    for (var id = 8920000; id <= 8920002; id++) {
        var boss = map.getMonsterById(id);
        if (boss != null && boss.isAlive()) return true;
    }
    return false;
}

function monsterKilled(mob, eim) {
    if (isQueen(mob) && !hasAliveQueen(mob.getMap()) && eim.getIntProperty("defeatedBoss") == 0) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        clearPQ(eim);

        mob.getMap().broadcastZakumVictory();
    }
    // 宝箱击杀：仅提示，不触发通关逻辑
    if (mob.getId() == treasureMobId) {
        eim.dropMessage(5, "[远征队] 宝箱已被击破！");
    }
}

/**
 * 所有怪物死亡时触发
 * - BOSS被击杀后（defeatedBoss=1），首次触发时召唤宝箱怪物
 * - 宝箱被击杀后再次触发时，treasureSpawned=1 阻止重复召唤
 */
function allMonstersDead(eim) {
    if (eim.getIntProperty("defeatedBoss") == 1 && eim.getIntProperty("treasureSpawned") == 0) {
        eim.setIntProperty("treasureSpawned", 1);
        var map = eim.getMapInstance(entryMap);
        var treasureMob = LifeFactory.getMonster(treasureMobId);
        map.spawnMonsterOnGroundBelow(treasureMob, new java.awt.Point(60, 134));
        eim.dropMessage(5, "[远征队] 神秘的宝箱出现了！");
    }
}

function cancelSchedule() {}

function updateGateState(newState) {
    var reactor = em.getChannelServer().getMapFactory().getMap(105200000).getReactorById(2118002);
    if (reactor != null) reactor.forceHitReactor(newState);
}

function dispose(eim) {
    if (!eim.isEventCleared()) {
        updateGateState(0);
    }
}

function partyPlayersCheck(eim, player) {
    if (eim.isExpeditionTeamLackingNow(true, minPlayers, player)) {
        eim.unregisterPlayer(player);
        eim.dropMessage(5, "[远征队] 队长已退出远征或者队伍人数不足最低要求，无法继续。");
        end(eim);
        return false;
    } else {
        eim.dropMessage(5, "[远征队] " + player.getName() + " 已离开副本。");
        eim.unregisterPlayer(player);
        return true;
    }
}
