/*
    AkayrumFSB - 十字猎人·阿卡伊勒分身 副本事件
    基于 Cygnus Battle 模板改写 + 自定义API兼容层
*/

var isPq = true;
var minPlayers = 1, maxPlayers = 1;
var minLevel = 140, maxLevel = 255;
var entryMap = 272010200;
var exitMap = 272010000;
var recruitMap = 272010000;
var clearMap = 272010000;

var minMapId = 272010200;
var maxMapId = 272010200;

var eventTime = 30;

const maxLobbies = 1;

var bossMobId = 8860001;
var guideNpcId = 2144000;

// 顶层常量：供 setup / spawnBoss / playerEntry 共用，避免各函数重复定义导致作用域错误
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
const Point = Java.type('java.awt.Point');
// var completeQuestId = 0;  // TODO: 如需通关任务，在此填任务ID并在 monsterKilled 中启用

function log(msg) {
    java.lang.System.out.println("[AkayrumFSB] " + msg);
}
function logErr(msg, err) {
    java.lang.System.out.println("[AkayrumFSB] ERROR: " + msg);
    if (err) {
        java.lang.System.out.println("[AkayrumFSB] " + err.toString());
        if (err.stack) java.lang.System.out.println("[AkayrumFSB] " + err.stack);
    }
}

function init() {
    em.setProperty("state", "0");
    em.setProperty("leader", "true");
    setEventRequirements();
    log("init() 完成");
}

function getMaxLobbies() {
    return maxLobbies;
}

function setEventRequirements() {
    var reqStr = "";

    reqStr += "\r\n   组队人数: ";
    reqStr += minPlayers;

    reqStr += "\r\n   等级要求: ";
    reqStr += minLevel + " ~ " + maxLevel;

    reqStr += "\r\n   时间限制: ";
    reqStr += eventTime + " 分钟";

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
    log("setup() channel=" + channel);

    var eim = em.newInstance("AkayrumFSB" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);

    em.setProperty("state", 1);
    em.setProperty("leader", "true");

    // 对齐已验证可用的 LNHXBOSS 写法：在 setup 内用 getInstanceMap 创建实例地图 +
    // resetPQ 重置 + 立即 spawnBoss（GM 已验证 8860001 可正常召唤、WZ 无问题）。
    // 整段包 try/catch，确保即便地图初始化异常也不会炸 setup 导致进不去副本。
    try {
        var level = 1;
        var map = eim.getInstanceMap(entryMap);
        map.resetPQ(level);
        // 锚点 y=-100 在地面(y≈71)上方，spawnMonsterOnGroundBelow 才能往下找到平台落脚
        spawnBoss(map, new Point(360, -100));
    } catch (e) {
        logErr("setup() 地图初始化/刷Boss 异常(进图后 playerEntry 会兜底补刷)", e);
    }

    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    log("setup() 完成, 计时器已启动 " + eventTime + "分钟");

    return eim;
}

function spawnBoss(map, anchor) {
    var mob;
    try {
        mob = LifeFactory.getMonster(bossMobId);
    } catch (e) {
        logErr("spawnBoss() getMonster(" + bossMobId + ") 抛出异常", e);
        return;
    }
    if (mob == null) {
        logErr("spawnBoss() ★ 无法生成Boss " + bossMobId + " — getMonster 返回 null", null);
        return;
    }

    // ★ 根因修复：spawnMonsterOnGroundBelow 内部 calcPointBelow 是从给定点“向下”找平台，
    // 因此给定点的 y 必须在平台“上方”（y 更小）。地图 272010200 地面约在 y=71，
    // 之前用 (360,100) 落在地面下方 → calcPointBelow 返回 null → NPE，Boss 永远刷不出。
    // 统一用“玩家所在平台上方”的锚点，确保 Boss 落在该平台上（可见、可打）。
    if (anchor == null) anchor = new Point(360, -100);

    try {
        map.spawnMonsterOnGroundBelow(mob, anchor);
        log("spawnBoss() Boss " + bossMobId + " 已生成(落地) at (" + anchor.x + "," + anchor.y + ")");
    } catch (e) {
        logErr("spawnMonsterOnGroundBelow 失败, 改用 spawnMonster(monster,mobTime,pos) 定点生成", e);
        try {
            // 本服 MapleMap.spawnMonster 三参重载为 (Monster, int mobTime, Point)
            // （对照 reactor 脚本的 spawnMonster(id, x, y) 三参写法，mobTime 传 0）
            map.spawnMonster(mob, 0, new Point(anchor.x, 71));
            log("spawnBoss() Boss " + bossMobId + " 已生成(定点) at x=" + anchor.x + " y=71");
        } catch (e2) {
            logErr("spawnMonster 也失败 — Boss 未能生成", e2);
        }
    }
}

// 检测地图实例内是否已存在目标 Boss（id = bossMobId），用于进图兜底补刷时避免重复
function bossOnMap(map) {
    try {
        var mobs = map.getMonsters();
        for (var i = 0; i < mobs.size(); i++) {
            if (mobs.get(i).getId() == bossMobId) return true;
        }
    } catch (e) {
        logErr("bossOnMap() 读取怪物列表失败", e);
    }
    return false;
}

function playerEntry(eim, player) {
    log("playerEntry() player=" + player.getName());

    // 玩家进入的实例地图：必须与 setup 内 getInstanceMap 创建的是同一个（已验证 LNHXBOSS 模式）
    var map = eim.getMapInstance(entryMap);

    // 兜底：若 setup 内刷 Boss 因任何原因失败（如实例不一致），进图前检测地图内
    // 是否已有 8860001，没有则补刷，确保玩家一定看得到 Boss。GM 已验证该地图可正常召唤。
    // 锚点取 0 号传送点（玩家进图落点）所在平台上方，Boss 必落在玩家脚下平台，可见可打。
    try {
        if (!bossOnMap(map)) {
            var anchor = new Point(360, -100);
            try {
                var pp = map.getPortal(0).getPosition();
                if (pp != null) anchor = new Point(pp.x, pp.y - 120);
            } catch (e3) {
                logErr("playerEntry() 读取传送点位置失败, 回退默认锚点(360,-100)", e3);
            }
            spawnBoss(map, anchor);
        } else {
            log("playerEntry() 地图已存在 Boss, 跳过补刷");
        }
    } catch (e) {
        logErr("playerEntry() 兜底刷Boss 异常(不影响进图)", e);
    }

    player.changeMap(map, map.getPortal(0));

    // 进图成功后再发送提示，避免"提示已进入但实际没进"的误报
    eim.dropMessage(5, "[十字猎人] " + player.getName() + " 已进入阿卡伊勒分身副本。");
}

function scheduledTimeout(eim) {
    log("scheduledTimeout()");
    end(eim);
}

function changedMap(eim, player, mapid) {
    log("changedMap() player=" + player.getName() + " mapid=" + mapid);
    if (mapid < minMapId || mapid > maxMapId) {
        playerExit(eim, player);
        end(eim);
    }
}

function changedLeader(eim, leader) {}

function playerDead(eim, player) {}

function playerRevive(eim, player) {
    return false;
}

function playerDisconnected(eim, player) {
    log("playerDisconnected() player=" + player.getName());
    playerExit(eim, player);
    end(eim);
    return 0;
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
    log("end()");

    var party = eim.getPlayers();
    for (var i = 0; i < party.size(); i++) {
        try {
            playerExit(eim, party.get(i));
        } catch (e) {
            try { party.get(i).changeMap(exitMap, 0); } catch (e2) {}
        }
    }

    em.setProperty("state", "0");
    try { eim.dispose(); } catch (e) { logErr("dispose 失败(可能已释放)", e); }
    log("end() 完成, state已重置为0");
}

function giveRandomEventReward(eim, player) {
    eim.giveEventReward(player);
}

function clearPQ(eim) {
    log("clearPQ()");
    eim.stopEventTimer();
    eim.setEventCleared();
    eim.startEventTimer(2 * 60000);  // 通关后2分钟自动退场
}

function monsterKilled(mob, eim) {
    log("monsterKilled() mobId=" + mob.getId() + " bossMobId=" + bossMobId);

    if (eim.isEventCleared()) return;
    if (mob.getId() != bossMobId) return;

    eim.setIntProperty("defeatedBoss", 1);
    try { eim.showClearEffect(mob.getMap().getId()); } catch (e) {}

    var players = eim.getPlayers();
    for (var i = 0; i < players.size(); i++) {
        var p = players.get(i);

        // 剧情特效：天气播报
        try {
            p.getAPI().getWeatherEffectNotice("因为你这种小东西的存在，我错过了等待了数百年的机会……！！", 67, 8000, 1);
        } catch (e) { logErr("getWeatherEffectNotice 失败", e); }

        // 引导NPC登场
        try {
            p.getAPI().npc_ChangeController(guideNpcId, "oid=1", -186, 71, 0);
        } catch (e) { logErr("npc_ChangeController 失败", e); }

        // 如需通关任务，取消下面注释并填好 completeQuestId
        // if (typeof completeQuestId !== 'undefined' && completeQuestId > 0) {
        //     try { p.forceCompleteQuest(completeQuestId); } catch (e) {}
        // }

        try { p.dropMessage(5, "阿卡伊勒分身已被击败！"); } catch (e) {}
    }

    eim.clearPQ();
    log("monsterKilled() Boss已击败, 事件通关");
}

function allMonstersDead(eim) {}

function cancelSchedule() {}

function dispose(eim) {
    log("dispose()");
}

// ==================== 工具函数 ====================

function warp(eim, mapId, portal) {
    for (var i = 0; i < eim.getPlayerCount(); i++) {
        try { eim.getPlayers().get(i).getAPI().warp(mapId, portal); } catch (e) {}
    }
}

function openNpc(eim, npcId, script) {
    for (var i = 0; i < eim.getPlayerCount(); i++) {
        try { eim.getPlayers().get(i).getAPI().openNpc(npcId, script); } catch (e) {}
    }
}

function randomNum(b, a) {
    switch (arguments.length) {
        case 1:
            return parseInt(Math.random() * b + 1, 10);
        case 2:
            return parseInt(Math.random() * (a - b + 1) + b, 10);
        default:
            return 0;
    }
}

// ==================== 自定义API兼容层 ====================
// 服务端可能走 onXxx 路径，这里委托给上方标准实现，确保两条路径都能正确处理

function onPlayerRegistered(eim, player) {
    playerEntry(eim, player);
}

function onMapChanged(eim, player, mapid) {
    changedMap(eim, player, mapid);
}

function onMonsterKilled(eim, mob) {
    monsterKilled(mob, eim);
    return 1;
}

function onTimeOut(eim) {
    scheduledTimeout(eim);
}

function onPlayerDisconnected(eim, player) {
    playerDisconnected(eim, player);
}

function onPlayerRevived(eim, player) {
    return playerRevive(eim, player);
}

function onPartyDisbanded(eim) {
    disbandParty(eim);
}

function onPlayerKilled(eim, player) {
    playerDead(eim, player);
}

function onItemPickedUp() {}

function onMonsterDamaged() {}