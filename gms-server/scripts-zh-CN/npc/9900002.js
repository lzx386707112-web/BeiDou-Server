/*
    多地图BOSS召唤 NPC (9900002)
    - 根据不同地图召唤不同BOSS
    - 支持门票消耗（DEBUG模式可关闭）
    - 每天每人召唤次数限制（按配置区分）
    - 参照 VanLeon_ExpeditionEnter.js / custom9600086Boss.js 的召唤方式
*/

// ====== 调试开关（true=不消耗道具、不计次数） ======
// var DEBUG = true;
var DEBUG = false;
// ====== BOSS配置数组 ======
// mapId:    地图ID
// bossId:   BOSS ID
// bossName: BOSS名称
// ticketId: 门票道具ID（0=无需门票）
// dailyLimit: 每天每人最多召唤次数
// spawnX / spawnY: 出生坐标
var BOSS_CONFIGS = [
    { mapId: 211070100, bossId: 8840000, bossName: "班·雷昂",  ticketId: 4001254, dailyLimit: 3, spawnX: -300, spawnY: -192 },
    // { mapId: 703011000, bossId: 9600086, bossName: "钻机BOSS", ticketId: 4001254, dailyLimit: 3, spawnX: -120, spawnY: 83 },
    { mapId: 703011000, bossId: 9600087, bossName: "钻机BOSS", ticketId: 4001254, dailyLimit: 3, spawnX: -120, spawnY: 83 }
];

var FREE_MARKET_ID = 910000000;
var COUNT_KEY_PREFIX = "BOSS_COUNT_";  // 每日次数Key前缀，每天自动清空

var status = 0;
var matchedConfigs = [];   // 当前地图匹配的配置索引数组
var selectedConfigIdx = -1;
var page = 0;
var selectedBoss = null;
var PAGE_SIZE = 12;

var LifeFactory = Java.type("org.gms.server.life.LifeFactory");
var BotBossCombatManager = Java.type("soloMapling.ArtificialPlayer.BotBossCombatManager");
var Point = Java.type("java.awt.Point");

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode < 0) {
        cm.dispose();
        return;
    }
    if (mode == 0) {
        cm.dispose();
        return;
    }
    status++;

    if (status == 0) {
        if (cm.getMapId() == FREE_MARKET_ID) {
            page = 0;
            sendFreeMarketBossPage();
            return;
        }

        // ---- 筛选当前地图可用的BOSS配置 ----
        var mapId = cm.getMapId();
        matchedConfigs = [];
        for (var i = 0; i < BOSS_CONFIGS.length; i++) {
            if (BOSS_CONFIGS[i].mapId == mapId) {
                matchedConfigs.push(i);
            }
        }

        if (matchedConfigs.length == 0) {
            cm.sendOk("该地图没有可召唤的BOSS。");
            cm.dispose();
            return;
        }

        // ---- 构建菜单 ----
        var menu = "#b请选择要执行的操作：#k\r\n\r\n";
        for (var j = 0; j < matchedConfigs.length; j++) {
            var cfg = BOSS_CONFIGS[matchedConfigs[j]];
            var remaining = getDailyRemaining(matchedConfigs[j]);

            var ticketStr = "";
            if (cfg.ticketId > 0) {
                ticketStr = " (需要 #v" + cfg.ticketId + "##z" + cfg.ticketId + "# 1个)";
            }
            if (DEBUG) {
                ticketStr = " [#d调试模式，免门票#k]";
            }
            menu += "#L" + j + "# 召唤 #r" + cfg.bossName + "#k" + ticketStr + " [今日剩余:#b" + remaining + "#k/#b" + cfg.dailyLimit + "#k]#l\r\n";
        }

        // 调试模式下显示清除BOSS选项
        if (DEBUG) {
            menu += "\r\n#d----- 调试: 清除地图BOSS -----#k\r\n";
            for (var k = 0; k < matchedConfigs.length; k++) {
                var clearCfg = BOSS_CONFIGS[matchedConfigs[k]];
                var exists = cm.getMap().getMonsterById(clearCfg.bossId) != null;
                var existsStr = exists ? " [#g已存在#k]" : " [#r不存在#k]";
                menu += "#L" + (matchedConfigs.length + 1 + k) + "# 清除 " + clearCfg.bossName + existsStr + "#l\r\n";
            }
        }

        menu += "\r\n#L" + matchedConfigs.length + "# 传送到自由市场#l";
        cm.sendSimple(menu);

    } else if (status == 1) {
        if (cm.getMapId() == FREE_MARKET_ID) {
            handleFreeMarketSelection(selection);
            return;
        }

        if (selection < matchedConfigs.length) {
            // ========== 召唤BOSS ==========
            selectedConfigIdx = matchedConfigs[selection];
            var cfg = BOSS_CONFIGS[selectedConfigIdx];
            var map = cm.getMap();

            // 检查BOSS是否已存在
            if (map.getMonsterById(cfg.bossId) != null) {
                cm.sendOk(cfg.bossName + "已经出现了！");
                cm.dispose();
                return;
            }

            // 检查每日次数（DEBUG模式跳过）
            if (!DEBUG && getDailyRemaining(selectedConfigIdx) <= 0) {
                cm.sendOk("你今天召唤" + cfg.bossName + "的次数已经用完了！(每日限制:#b" + cfg.dailyLimit + "#k次)");
                cm.dispose();
                return;
            }

            // 检查门票（DEBUG模式跳过）
            if (!DEBUG && cfg.ticketId > 0 && !cm.haveItem(cfg.ticketId, 1)) {
                cm.sendOk("你没有 #v" + cfg.ticketId + "##z" + cfg.ticketId + "#，无法召唤" + cfg.bossName + "！");
                cm.dispose();
                return;
            }

            // 二次确认
            var confirmMsg = "确定要召唤 #r" + cfg.bossName + "#k 吗？";
            if (!DEBUG && cfg.ticketId > 0) {
                confirmMsg += "\r\n将消耗 1个 #v" + cfg.ticketId + "##z" + cfg.ticketId + "#";
            }
            if (DEBUG) {
                confirmMsg += "\r\n#d(调试模式，不消耗道具，不计次数)#k";
            } else {
                confirmMsg += "\r\n召唤后今日剩余次数:#b" + (getDailyRemaining(selectedConfigIdx) - 1) + "#k/#b" + cfg.dailyLimit + "#k";
            }
            cm.sendYesNo(confirmMsg);

        } else if (DEBUG && selection > matchedConfigs.length && selection <= matchedConfigs.length * 2) {
            // ========== 清除BOSS（仅DEBUG模式显示） ==========
            var clearIdx = matchedConfigs[selection - matchedConfigs.length - 1];
            var clearCfg = BOSS_CONFIGS[clearIdx];
            var map = cm.getMap();

            if (map.getMonsterById(clearCfg.bossId) == null) {
                cm.sendOk("地图上没有 " + clearCfg.bossName + "！");
            } else {
                map.killMonster(clearCfg.bossId);
                cm.getPlayer().dropMessage(5, "已清除地图上的 " + clearCfg.bossName + "！");
                cm.sendOk("已清除地图上的 " + clearCfg.bossName + "！");
            }
            cm.dispose();

        } else if (selection == matchedConfigs.length) {
            // 传送到自由市场
            cm.warp(FREE_MARKET_ID);
            cm.dispose();
        }

    } else if (status == 2) {
        if (cm.getMapId() == FREE_MARKET_ID) {
            summonFreeMarketBoss();
            cm.dispose();
            return;
        }

        var cfg = BOSS_CONFIGS[selectedConfigIdx];
        var map = cm.getMap();

        // 消耗门票（DEBUG模式跳过）
        if (!DEBUG && cfg.ticketId > 0) {
            cm.gainItem(cfg.ticketId, -1);
        }

        // 记录每日次数（DEBUG模式跳过）
        if (!DEBUG) {
            addDailyCount(selectedConfigIdx);
        }

        // 召唤BOSS（与 VanLeon_ExpeditionEnter.js / custom9600086Boss.js 一致的方式）
        var mob = LifeFactory.getMonster(cfg.bossId);
        map.spawnMonsterOnGroundBelow(mob, new Point(cfg.spawnX, cfg.spawnY));
        cm.getPlayer().dropMessage(5, cfg.bossName + " 出现了！");

        cm.dispose();
    }
}

// ==================== 每日次数管理（getAccountExtendValue + true 自动每日清空） ====================

function getCountKey(configIdx) {
    var cfg = BOSS_CONFIGS[configIdx];
    return COUNT_KEY_PREFIX + cfg.bossId + "_" + cfg.mapId;
}

function getDailyUsed(configIdx) {
    var v = cm.getAccountExtendValue(getCountKey(configIdx), true);
    if (v == null || v === "") {
        return 0;
    }
    return parseInt(v, 10) || 0;
}

function getDailyRemaining(configIdx) {
    var cfg = BOSS_CONFIGS[configIdx];
    if (cfg.dailyLimit <= 0) return 0;
    return cfg.dailyLimit - getDailyUsed(configIdx);
}

function addDailyCount(configIdx) {
    var used = getDailyUsed(configIdx) + 1;
    cm.saveOrUpdateAccountExtendValue(getCountKey(configIdx), String(used), true);
}

// ==================== 自由市场：全 Boss 列表召唤 ====================

function sendFreeMarketBossPage() {
    var bosses = LifeFactory.getBossSummonList();
    if (bosses == null || bosses.size() == 0) {
        cm.sendOk("没有找到可召唤的 Boss。");
        cm.dispose();
        return;
    }

    var maxPage = Math.floor((bosses.size() - 1) / PAGE_SIZE);
    if (page > maxPage) {
        page = maxPage;
    }

    var start = page * PAGE_SIZE;
    var end = Math.min(start + PAGE_SIZE, bosses.size());
    var text = "#e自由市场 Boss 召唤#n\r\n";
    text += "当前页：" + (page + 1) + " / " + (maxPage + 1) + "，共 " + bosses.size() + " 个 Boss。\r\n";
    text += "召唤后假人会自动开始集火，Boss 死亡前不能召唤新的。\r\n\r\n";

    for (var i = start; i < end; i++) {
        var boss = bosses.get(i);
        text += "#L" + i + "##b" + bossLabel(boss) + "#k#l\r\n";
    }
    text += "\r\n";
    if (page > 0) {
        text += "#L9000#上一页#l\r\n";
    }
    if (page < maxPage) {
        text += "#L9001#下一页#l\r\n";
    }
    cm.sendSimple(text);
}

function handleFreeMarketSelection(selection) {
    var bosses = LifeFactory.getBossSummonList();
    if (selection == 9000) {
        page = Math.max(0, page - 1);
        status = 0;
        sendFreeMarketBossPage();
        return;
    }
    if (selection == 9001) {
        page++;
        status = 0;
        sendFreeMarketBossPage();
        return;
    }
    if (selection < 0 || selection >= bosses.size()) {
        cm.sendOk("这个 Boss 暂时不可召唤。");
        cm.dispose();
        return;
    }
    selectedBoss = bosses.get(selection);
    cm.sendYesNo("确定要在自由市场召唤 #r" + bossLabel(selectedBoss) + "#k 吗？\r\n\r\n同一时间市场只允许存在一只 Boss。");
}

function summonFreeMarketBoss() {
    if (selectedBoss == null) {
        cm.sendOk("请选择一个 Boss。");
        return;
    }

    var map = cm.getMap();
    if (map.countBosses() > 0) {
        cm.sendOk("当前市场已经存在 Boss，先击败它再召唤新的。");
        return;
    }

    var monster = LifeFactory.getMonster(selectedBoss.getId());
    if (monster == null || !monster.isBoss()) {
        cm.sendOk("这个怪物不是 Boss，已取消召唤。");
        return;
    }

    var playerPos = cm.getPlayer().getPosition();
    var spawnX = playerPos.x + (cm.getPlayer().isFacingLeft() ? -180 : 180);
    map.spawnMonsterOnGroundBelow(monster, new Point(spawnX, playerPos.y));
    BotBossCombatManager.handleChatTrigger(cm.getPlayer(), "假人打boss");
    cm.sendOk("已召唤 #r" + bossLabel(selectedBoss) + "#k。\r\n假人已经开始集火攻击。");
}

function bossLabel(boss) {
    return boss.getName() + " [" + boss.getId() + "] Lv." + boss.getLevel() + " HP " + formatNumber(boss.getHp());
}

function formatNumber(value) {
    var str = String(value);
    var out = "";
    while (str.length > 3) {
        out = "," + str.substring(str.length - 3) + out;
        str = str.substring(0, str.length - 3);
    }
    return str + out;
}
