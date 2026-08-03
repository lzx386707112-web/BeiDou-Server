/**
 * @author: Ronan
 * @event: PIERRE Battle
 * @optimized: 北斗GMS083 适配优化
 * @modified: 添加三阶段变身机制 (8900100 → 8900101 → 8900102 → 8900100)
 *
 * 变身流程:
 *   Phase 0: 8900100 HP <= 70% → 变身为 8900101，继承当前血量
 *   Phase 1: 8900101 HP <= 30% → 变身为 8900102，继承当前血量
 *   Phase 2: 8900102 HP <= 5%  → 变回 8900100，继承当前血量
 *   Phase 3: 8900100 死亡 → 通关
 *
 * 技术要点:
 *   - 使用 eim.schedule() 每500ms轮询BOSS血量
 *   - 用 addHp() 减少新怪物HP到继承值（保持maxHP不变，HP条显示正确百分比）
 *   - 用 isTransforming 标记防止变身 killMonster 触发 monsterKilled 通关逻辑
 *   - 变身时先 spawn 新怪物（注册到 EIM mobs 列表），再 kill 旧怪物（避免 allMonstersDead 误触发）
 *   - 变身后用 broadcastMobHpBar 广播更新HP条
 */

var isPq = true;
var minPlayers = 1, maxPlayers = 30;
var minLevel = 125, maxLevel = 255;
var entryMap = 105200211;
var entryItem = 4033611;    // 入场消耗道具
var exitMap = 105200000;
var recruitMap = 105200000;
var clearMap = 105200000;
var minMapId = 105200211;
var maxMapId = 105200211;
var eventTime = 120;     // 120 minutes
const maxLobbies = 1;

const GameConfig = Java.type('org.gms.config.GameConfig');
const LifeFactory = Java.type('org.gms.server.life.LifeFactory');

minPlayers = GameConfig.getServerBoolean("use_enable_solo_expeditions") ? 1 : minPlayers;
if (GameConfig.getServerBoolean("use_enable_party_level_limit_lift")) {
    minLevel = 125, maxLevel = 200;
}

var bossId = 8900100;         // 皮埃尔 BOSS (初始形态 / 最终形态)
var treasureMobId = 8900103;  // 宝箱怪物

// === 变身配置 ===
var phase1MobId = 8900101;    // 第一阶段变身目标
var phase2MobId = 8900102;    // 第二阶段变身目标
// 第三阶段变回 bossId (8900100)

// HP 阈值（占当前 maxHP 的比例）
var PHASE1_THRESHOLD = 0.80;  // 80% → 触发第一次变身
var PHASE2_THRESHOLD = 0.50;  // 50% → 触发第二次变身
var PHASE3_THRESHOLD = 0.10;  // 10%  → 触发第三次变身（变回原形）

// HP 轮询间隔（毫秒）
var HP_CHECK_INTERVAL = 500;

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
    var eim = em.newInstance("PIERRE" + channel);
    eim.setProperty("canJoin", 1);
    eim.setProperty("defeatedBoss", 0);
    eim.setProperty("treasureSpawned", 0);

    // === 变身状态初始化 ===
    eim.setProperty("bossPhase", "0");       // 0=初始8900100, 1=8900101, 2=8900102, 3=最终8900100
    eim.setProperty("isTransforming", "0");   // 变身标记，防止 killMonster 触发通关

    var level = 1;
    var battleMap = eim.getInstanceMap(entryMap);
    battleMap.resetPQ(level);
    battleMap.killAllMonsters();

    // 自动召唤 皮埃尔 BOSS
    var mob = LifeFactory.getMonster(bossId);
    battleMap.spawnMonsterOnGroundBelow(mob, new java.awt.Point(-131, 550));

    // 启动 HP 轮询监控
    eim.schedule("checkBossHp", HP_CHECK_INTERVAL);

    eim.startEventTimer(eventTime * 60000);
    setEventRewards(eim);
    setEventExclusives(eim);
    return eim;
}

// ============================
// === 变身核心逻辑 ===
// ============================

/**
 * HP 轮询函数 - 由 eim.schedule 定时调用
 * 检查当前BOSS血量，达到阈值时触发变身
 */
function checkBossHp(eim) {
    // 事件已结束或已通关，停止监控
    if (eim.isEventDisposed()) return;

    var phase = eim.getIntProperty("bossPhase");
    // 最终阶段不再变身
    if (phase >= 3) return;

    // 获取当前阶段的怪物ID
    var currentMobId = getBossIdByPhase(phase);
    var map = eim.getMapInstance(entryMap);
    var boss = map.getMonsterById(currentMobId);

    // BOSS不存在或已死亡，停止监控
    if (boss == null || !boss.isAlive()) return;

    var hp = boss.getHp();
    var maxHp = boss.getMobMaxHp();
    if (maxHp <= 0) return;

    var hpPercent = hp / maxHp;

    // 检查变身阈值
    if (phase == 0 && hpPercent <= PHASE1_THRESHOLD) {
        transformBoss(eim, boss, phase1MobId, 1);
    } else if (phase == 1 && hpPercent <= PHASE2_THRESHOLD) {
        transformBoss(eim, boss, phase2MobId, 2);
    } else if (phase == 2 && hpPercent <= PHASE3_THRESHOLD) {
        transformBoss(eim, boss, bossId, 3);
    }

    // 继续监控（除非已进入最终阶段）
    phase = eim.getIntProperty("bossPhase");
    if (phase < 3 && !eim.isEventDisposed()) {
        eim.schedule("checkBossHp", HP_CHECK_INTERVAL);
    }
}

/**
 * 根据阶段获取对应怪物ID
 */
function getBossIdByPhase(phase) {
    if (phase == 0) return bossId;       // 8900100
    if (phase == 1) return phase1MobId;  // 8900101
    if (phase == 2) return phase2MobId;  // 8900102
    if (phase == 3) return bossId;       // 8900100 (最终)
    return bossId;
}

/**
 * 执行BOSS变身
 * 1. 记录旧BOSS当前血量
 * 2. 在地图上生成新怪物（此时新怪物已注册到 EIM mobs 列表）
 * 3. 用 addHp 将新怪物HP减少到继承值（保持maxHP不变）
 * 4. 广播HP条更新
 * 5. 移除旧BOSS（killMonster 会触发 monsterKilled，但 isTransforming 标记会拦截）
 * 6. 更新阶段状态
 *
 * @param eim        事件实例
 * @param oldBoss    旧BOSS Monster对象
 * @param newMobId   新怪物ID
 * @param newPhase   新阶段编号 (1/2/3)
 */
function transformBoss(eim, oldBoss, newMobId, newPhase) {
    // 设置变身标记，防止 killMonster 触发 monsterKilled/allMonstersDead
    eim.setProperty("isTransforming", "1");

    // 记录旧BOSS当前血量
    var inheritedHp = oldBoss.getHp();
    if (inheritedHp < 1) inheritedHp = 1;  // 最低保留1点血

    // 记录旧BOSS位置
    var oldPos = oldBoss.getPosition();
    var spawnPos = new java.awt.Point(oldPos.x, oldPos.y);

    var map = eim.getMapInstance(entryMap);

    // 1. 生成新怪物
    var newMob = LifeFactory.getMonster(newMobId);
    map.spawnMonsterOnGroundBelow(newMob, spawnPos);

    // 2. 将新怪物HP减少到继承值
    //    addHp(负值) = 减少HP，保持 maxHP 不变
    //    这样HP条会显示正确的百分比（如70%），而不是满血
    var newMaxHp = newMob.getMobMaxHp();
    if (inheritedHp < newMaxHp) {
        // 新怪物maxHP > 继承HP，需要减少
        newMob.addHp(-(newMaxHp - inheritedHp));
    } else if (inheritedHp > newMaxHp) {
        // 继承HP > 新怪物maxHP（不同怪物maxHP不同时），截断到maxHP
        // 不需要操作，当前HP已经是maxHP
    }
    // 如果 inheritedHp == newMaxHp，不需要操作

    // 3. 广播HP条更新给所有玩家
    //    spawnMonsterOnGroundBelow 内部已广播过一次满血HP条
    //    这里用 broadcastMobHpBar 修正为实际HP
    if (newMob.hasBossHPBar()) {
        var players = eim.getPlayers();
        for (var i = 0; i < players.size(); i++) {
            newMob.broadcastMobHpBar(players.get(i));
        }
    }

    // 4. 移除旧BOSS
    //    killMonster(monster, null, false):
    //    - killer=null → 走"无击杀者"路径，不掉落物品
    //    - false → 不掉落
    //    - 会调用 dispatchMonsterKilled → eim.monsterKilled → 脚本 monsterKilled
    //    - 但 isTransforming=1 会拦截，直接 return
    //    - 新怪物已在 mobs 列表中，所以 allMonstersDead 不会触发
    map.killMonster(oldBoss, null, false);

    // 5. 更新阶段状态
    eim.setProperty("bossPhase", newPhase + "");
    eim.setProperty("isTransforming", "0");

    // 6. 广播变身提示
    var messages = {
        1: "[远征队] 皮埃尔吸收了黑暗能量，变身为第二形态！",
        2: "[远征队] 皮埃尔进入了狂暴状态，小心！",
        3: "[远征队] 皮埃尔恢复了原形，做最后的挣扎！"
    };
    eim.dropMessage(5, messages[newPhase] || "[远征队] 皮埃尔变了！");
}

// ============================
// === 原始逻辑（带变身拦截）===
// ============================

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
    eim.dropMessage(5, "[远征队] 恭喜！你们成功击败了 皮埃尔！");
    updateGateState(0);
    eim.startEventTimer(300000); // 通关后5分钟强制清场，注意此时无法重连
}

function isPierre(mob) {
    return mob.getId() == bossId;
}

/**
 * 怪物被击杀回调
 *
 * 关键：变身期间 (isTransforming=1) 的 killMonster 也会触发此回调
 *       必须用 isTransforming 标记拦截，否则变身时杀8900100会误触发通关
 *
 * 只有最终阶段(phase 3)的 8900100 被玩家击杀才触发通关
 * 初始阶段(phase 0)的 8900100 被玩家直接击杀也触发通关（玩家伤害够高，没等变身就打死）
 */
function monsterKilled(mob, eim) {
    // 变身期间的 killMonster 不处理
    if (eim.getIntProperty("isTransforming") == 1) return;

    // BOSS击杀：触发通关 + 伤害排名
    // 只有 8900100 的死亡触发通关（无论phase 0还是phase 3）
    if (isPierre(mob) && eim.getIntProperty("defeatedBoss") == 0) {
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
 *
 * 关键：变身期间不触发此逻辑
 *       因为变身时先spawn新怪物再kill旧怪物，mobs列表不为空，
 *       EIM 内部不会调用 allMonstersDead，但保险起见也加标记拦截
 */
function allMonstersDead(eim) {
    // 变身期间不处理
    if (eim.getIntProperty("isTransforming") == 1) return;

    // BOSS被击杀后（defeatedBoss=1），首次触发时召唤宝箱怪物
    // 宝箱被击杀后再次触发时，treasureSpawned=1 阻止重复召唤
    if (eim.getIntProperty("defeatedBoss") == 1 && eim.getIntProperty("treasureSpawned") == 0) {
        eim.setIntProperty("treasureSpawned", 1);
        var map = eim.getMapInstance(entryMap);
        var treasureMob = LifeFactory.getMonster(treasureMobId);
        map.spawnMonsterOnGroundBelow(treasureMob, new java.awt.Point(-131, 550));
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
