/**
 * @author: Ronan
 * @event: AKAYRUM Battle
 * @optimized: 北斗GMS083 适配优化
 */

var isPq = true;
var minPlayers = 2, maxPlayers = 30;
var minLevel = 140, maxLevel = 255;
var entryMap = 272030400;
//var entryItem = 4033611;    // 入场消耗道具
var exitMap = 272030300;
var recruitMap = 272030300;
var clearMap = 272030300;

var minMapId = 272030400;
var maxMapId = 272030400;

var eventTime = 120;     // 120 minutes

const maxLobbies = 1;

const GameConfig = Java.type('org.gms.config.GameConfig');
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');

minPlayers = GameConfig.getServerBoolean("use_enable_solo_expeditions") ? 1 : minPlayers;
if (GameConfig.getServerBoolean("use_enable_party_level_limit_lift")) {
    minLevel = 140, maxLevel = 200;
}


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
    var eim = em.newInstance("AKAYRUM" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);

    var level = 1;
    var battleMap = eim.getInstanceMap(entryMap);
    battleMap.resetPQ(level);
    battleMap.killAllMonsters();

    // 自动召唤 AKAYRUM BOSS (8860000)
    var mob = LifeFactory.getMonster(8860000);
    battleMap.spawnMonsterOnGroundBelow(mob, new java.awt.Point(-65, -195));

    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);

    return eim;
}

/**
 * 处理玩家进入远征副本事件 - 当玩家进入远征副本时触发
 * @param {ExpeditionInstanceManager} eim - 远征副本实例管理器
 * @param {Player} player - 进入副本的玩家对象
 * @returns {void}
 * @description 当玩家进入副本时发送系统消息，并将玩家传送到副本入口地图
 */
function playerEntry(eim, player) {
    eim.dropMessage(5, "[远征队] " + player.getName() + " 已进入副本地图。");

    var map = eim.getMapInstance(entryMap);

    player.changeMap(map, map.getPortal(0));


    // 扣除入场道具（gainItem 在 AbstractPlayerInteraction 上，需通过 getAbstractPlayerInteraction() 获取）
    //player.getAbstractPlayerInteraction().gainItem(entryItem, -0);
    //player.dropMessage(6, "消耗了入场道具 古树钥匙");
}

function scheduledTimeout(eim) {
    end(eim);
}

/**
 * 处理玩家切换地图事件 - 当玩家在远征副本中切换地图时触发
 * @param {ExpeditionInstanceManager} eim - 远征副本实例管理器
 * @param {Player} player - 触发事件的玩家对象
 * @param {number} mapid - 玩家切换到的地图ID
 * @returns {void}
 * @description 当玩家切换到副本允许范围外的地图时，执行玩家移除逻辑
 */
function changedMap(eim, player, mapid) {
    if (mapid < minMapId || mapid > maxMapId) {
        partyPlayersCheck(eim, player);
    }
}

function changedLeader(eim, leader) {}

function playerDead(eim, player) {}

/**
 * 处理玩家复活事件 - 当玩家在远征副本中复活时触发
 * @param {ExpeditionInstanceManager} eim - 远征副本实例管理器
 * @param {Player} player - 触发事件的玩家对象
 * @returns {void}
 */
function playerRevive(eim, player) {
    partyPlayersCheck(eim, player);
}

/**
 * 处理玩家断线事件 - 当玩家在远征副本中断开连接时触发
 * @param {ExpeditionInstanceManager} eim - 远征副本实例管理器
 * @param {Player} player - 触发事件的玩家对象
 * @returns {void}
 */
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
    eim.dropMessage(5, "[远征队] 恭喜！你们成功击败了 阿卡伊勒！");
    updateGateState(0);
    eim.startEventTimer(300000); // 通关后5分钟强制清场，注意此时无法重连
}

function isAKAYRUM(mob) {
    var mobid = mob.getId();
    return (mobid == 8860000);
}

function monsterKilled(mob, eim) {
    if (isAKAYRUM(mob) && eim.getIntProperty("defeatedBoss") == 0) {
        eim.setIntProperty("defeatedBoss", 1);
        eim.showClearEffect(mob.getMap().getId());
        clearPQ(eim);

        mob.getMap().broadcastZakumVictory();
    }
}

function allMonstersDead(eim) {}

function cancelSchedule() {}

function updateGateState(newState) {    // thanks Conrad for noticing missing gate update
    var reactor = em.getChannelServer().getMapFactory().getMap(272030300).getReactorById(2118002);
    if (reactor != null) reactor.forceHitReactor(newState);
}

function dispose(eim) {
    if (!eim.isEventCleared()) {
        updateGateState(0);
    }
}

/**
 * 检测队伍人数是否满足最低人数要求
 * @param {ExpeditionInstanceManager} eim - 远征副本实例管理器
 * @param {Player} player - 触发事件的玩家对象
 * @returns {void}
 */
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