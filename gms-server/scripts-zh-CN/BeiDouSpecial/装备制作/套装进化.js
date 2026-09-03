// ============================================================================
// 装备升级系统（重构版）
// 10阶段防具升级 · 80%成功率 · 全职业通用(阶段0-5) + 按职业分化(阶段6-9)
// 条件：材料·任务·指定怪物击杀·BOSS击杀·装备献祭·特殊物品(BOSS掉落)
// 击杀规则：提前击杀不计数，升级失败所有击杀数清零
// ============================================================================

var InventoryType = Java.type("org.gms.client.inventory.InventoryType");
var InventoryManipulator = Java.type("org.gms.client.inventory.manipulator.InventoryManipulator");
var ItemInformationProvider = Java.type("org.gms.server.ItemInformationProvider");
var Job = Java.type("org.gms.client.Job");
var Quest = Java.type("org.gms.server.quest.Quest");

// ---- 职业 ----
var JOB_NAMES = ["战士", "法师", "弓箭手", "飞侠", "海盗"];

// ---- 存档键 ----
var STAGE_KEY_PREFIX = "equip_upgrade_v2_stage_";
var KILL_KEY_PREFIX = "equip_upgrade_v2_kill_"; // + stageIdx + "_" + mobId

// ---- 升级成功率 ----
var UPGRADE_SUCCESS_RATE = 80; // 80%成功率

// ---- BOSS名称 ----
var BOSS_NAMES = {
    2220000:"红蜗牛王",3220000:"树妖王",3220001:"大宇",4220001:"歇尔夫",
    5220002:"浮士德",5220004:"巨型蜈蚣",5220000:"巨居蟹",5220001:"巨居蟹",5220003:"提莫",
    6220000:"多尔",6220001:"朱诺",6090002:"青竹武士",7220001:"九尾狐",
    7220000:"肯德熊",7220002:"妖怪禅师",8220000:"艾利杰",8850011:"希纳斯",
    8220002:"吉米拉",8220009:"小吃店",8860000:"阿卡伊勒",8220003:"大海兽",
    8910100:"半半",8900100:"皮埃尔",8920101:"血腥女王",8930100:"贝伦",
    8870000:"希拉",8870200:"白发希拉",8880400:"觉醒希拉",8880200:"卡翁",
    8645009:"敦凯尔",8880700:"守护天使绿水灵",8880803:"监视者卡洛斯",
    4130103:"战甲吹泡泡鱼",8130100:"蝙蝠怪",8220001:"驮狼雪人",
    8500002:"帕普拉图斯",9400014:"天球",9400121:"女老板",
    8220004:"多多",8220005:"玄冰独角兽",8220006:"雷卡",
    8800002:"扎昆",9400300:"大头头",8510000:"鱼王",
    9400549:"死灵骑士",9400575:"大脚",8150000:"蝙蝠魔",
    8810018:"暗黑龙王",8880142:"露希妲"
};

// ============================================================================
// 防具升级配置（10阶段）
// jobType:"all" = 全职业通用 | jobType:"byJob" = 按职业分化
// 条件：items, quests, killMobs, equipSacrifice, specialDrops
// 击杀规则：提前击杀不计数，升级失败所有击杀数清零
// ============================================================================
var ARMOR_STAGES = [
    // ============ 阶段0: Lv30 全职业通用 ============
    {name:"30级套装",level:30,jobType:"all",
     equips:{cap:1003922,longcoat:1052638,shoes:1072844,glove:1082536},
     conditions:{
        meso:10000000,cash:1000,
        items:[[4000007,100],[4000031,100],[4000039,100],[4000022,100],[1032000,1]],
        quests:[2010,2034,2023,2017],
        killMobs:[[1140100,100],[2130103,100],[3230300,100]],
        equipSacrifice:[],
        specialDrops:[{itemId:4031543,bossMobIds:[3220000,2220000],dropRate:5}]}},

    // ============ 阶段1: Lv45 全职业通用 ============
    {name:"45级套装",level:45,jobType:"all",
     equips:{cap:1003242,longcoat:1052357,shoes:1072521,glove:1082314},
     conditions:{
        meso:15000000,cash:2000,
        items:[[4000025,100],[4000021,100],[4000036,100],[4000032,100],[4000033,100],
               [4020000,10],[4020001,10],[4020002,10],[4020003,10],[4020004,10],
               [4020005,10],[4020006,10],[4020007,10],[4020008,10]],
        quests:[2070,2076,2072,2013,2028,2061],
        killMobs:[[4230125,100],[4230102,100],[4130100,100],[3230100,100]],
        equipSacrifice:[],
        specialDrops:[{itemId:4031544,bossMobIds:[5220002],dropRate:5}]}},

    // ============ 阶段2: Lv70 全职业通用 ============
    {name:"70级套装",level:70,jobType:"all",
     equips:{cap:1003243,longcoat:1052358,shoes:1072522,glove:1082315},
     conditions:{
        meso:50000000,cash:3000,
        items:[[4000048,100],[4000057,100],[4000063,100],[4000074,100]],
        quests:[2039,2043,2095,2119,2200],
        killMobs:[[6230601,100],[6230100,100],[6130208,100],[7130104,100],[6130209,100]],
        equipSacrifice:[],
        specialDrops:[{itemId:4031545,bossMobIds:[5220000],dropRate:5}]}},

    // ============ 阶段3: Lv80 全职业通用 ============
    {name:"80级套装",level:80,jobType:"all",
     equips:{cap:1003364,longcoat:1052405,shoes:1072610,glove:1082391},
     conditions:{
        meso:70000000,cash:3500,
        items:[[4000078,100],[4000081,100],[4000088,100],[4000096,100],[4000098,100],
               [4000109,100],[4000104,100],[4000117,100]],
        quests:[3202,3209,3220,3243,3434,3437],
        killMobs:[[2230103,100],[3230103,100],[3230304,100],[3230400,100],[6230300,100]],
        equipSacrifice:[],
        specialDrops:[{itemId:1002006,bossMobIds:[4130103],dropRate:3}]}},

    // ============ 阶段4: Lv100 全职业通用 ============
    {name:"100级套装",level:100,jobType:"all",
     equips:{cap:1003561,longcoat:1052467,shoes:1072672,glove:1082438},
     conditions:{
        meso:100000000,cash:5000,
        items:[],
        quests:[3615,3616,3617,3618,3630,3633,3094,3077,3082,6134],
        killMobs:[[8140600,100],[8140701,100],[8140702,100],[8141100,100],[8141300,100],
                  [9400013,100],[8140101,100],[8140111,100],[9400205,10]],
        equipSacrifice:[],
        specialDrops:[{itemId:1002761,bossMobIds:[7220001],dropRate:3},
                      {itemId:1004556,bossMobIds:[8130100],dropRate:3},
                      {itemId:1702598,bossMobIds:[8220001],dropRate:3}]}},

    // ============ 阶段5: Lv120 全职业通用 ============
    {name:"120级套装",level:120,jobType:"all",
     equips:{cap:1004549,longcoat:1052952,shoes:1073077,glove:1082658},
     conditions:{
        meso:200000000,cash:6000,
        items:[[4000147,100],[4000157,100],[4000168,100],[4000176,10],[4000240,100],
               [4011000,50],[4011001,50],[4011002,50],[4011003,50],[4011004,50],
               [4011005,50],[4011006,50]],
        quests:[3512,6263,3912,3908,3918,3923,3936,3954,3306,3317,6207],
        killMobs:[[9420530,100],[9420533,100],[9420538,100],[9420540,100],
                  [9400542,100],[9400562,100]],
        equipSacrifice:[],
        specialDrops:[]}},

    // ============ 阶段6: Lv140 按职业分化 ============
    {name:"140级套装",level:140,jobType:"byJob",
     warrior:{cap:1003172,longcoat:1052314,shoes:1072485,glove:1082295},
     mage:{cap:1003173,longcoat:1052315,shoes:1072486,glove:1082296},
     archer:{cap:1003174,longcoat:1052316,shoes:1072487,glove:1082297},
     thief:{cap:1003175,longcoat:1052317,shoes:1072488,glove:1082298},
     pirate:{cap:1003176,longcoat:1052318,shoes:1072489,glove:1082299},
     conditions:{
        meso:400000000,cash:7000,
        items:[[4021000,50],[4021001,50],[4021002,50],[4021003,50],[4021004,50],
               [4021005,50],[4021006,50],[4021007,50],[4021008,50]],
        quests:[3519],
        killMobs:[[8190004,100],[8200008,100],[8200010,100],
                  [8220003,3],[8500002,3],[9400014,3],[9400121,3],
                  [8220004,3],[8220005,3],[8220006,3]],
        equipSacrifice:[{itemId:1002972,count:1},{itemId:1042243,count:1},
                        {itemId:1072679,count:1},{itemId:1082393,count:1}],
        specialDrops:[]}},

    // ============ 阶段7: Lv160 按职业分化 ============
    {name:"160级套装",level:160,jobType:"byJob",
     warrior:{cap:1004422,longcoat:1052882,shoes:1073030,glove:1082636},
     mage:{cap:1004423,longcoat:1052887,shoes:1073032,glove:1082637},
     archer:{cap:1004424,longcoat:1052888,shoes:1073033,glove:1082638},
     thief:{cap:1004425,longcoat:1052889,shoes:1073034,glove:1082639},
     pirate:{cap:1004426,longcoat:1052890,shoes:1073035,glove:1082640},
     conditions:{
        meso:500000000,cash:7500,
        items:[[4021009,50],[4011007,50],[4011008,50],[4003002,100],
               [2012002,50],[4003000,50]],
        quests:[],
        killMobs:[[8800002,10],[9400300,10],[8510000,10],
                  [9400549,20],[9400575,20],[8150000,20]],
        equipSacrifice:[{itemId:1003540,count:1},{itemId:1052460,count:1},
                        {itemId:1072664,count:1},{itemId:1082432,count:1}],
        specialDrops:[]}},

    // ============ 阶段8: Lv200 按职业分化 ============
    {name:"200级套装",level:200,jobType:"byJob",
     warrior:{cap:1004808,longcoat:1053063,shoes:1073158,glove:1082695},
     mage:{cap:1004809,longcoat:1053064,shoes:1073159,glove:1082696},
     archer:{cap:1004810,longcoat:1053065,shoes:1073160,glove:1082697},
     thief:{cap:1004811,longcoat:1053066,shoes:1073161,glove:1082698},
     pirate:{cap:1004812,longcoat:1053067,shoes:1073162,glove:1082699},
     conditions:{
        meso:800000000,cash:8000,
        items:[[4005000,50],[4005002,50],[4005001,50],[4005003,50],[4251201,2]],
        quests:[],
        killMobs:[[8810018,10],
                  [8600000,100],[8600001,100],[8600002,100],[8600003,100],
                  [8600004,100],[8600005,100],[8600006,100],
                  [8610005,100],[8610006,100],[8610007,100],[8610008,100],[8610009,100],
                  [8610010,100],[8610011,100],[8610012,100],[8610013,100],[8610014,100]],
        equipSacrifice:[],
        equipSacrificeByJob:[
            [{itemId:1005196,count:1},{itemId:1052804,count:1},{itemId:1042254,count:1},{itemId:1072967,count:1},{itemId:1082593,count:1}],
            [{itemId:1005197,count:1},{itemId:1052805,count:1},{itemId:1042255,count:1},{itemId:1072968,count:1},{itemId:1082594,count:1}],
            [{itemId:1005198,count:1},{itemId:1052806,count:1},{itemId:1042256,count:1},{itemId:1072969,count:1},{itemId:1082595,count:1}],
            [{itemId:1005199,count:1},{itemId:1052807,count:1},{itemId:1042257,count:1},{itemId:1072970,count:1},{itemId:1082596,count:1}],
            [{itemId:1005200,count:1},{itemId:1052808,count:1},{itemId:1042258,count:1},{itemId:1072971,count:1},{itemId:1082597,count:1}]
        ],
        specialDrops:[]}},

    // ============ 阶段9: 永恒套装 按职业分化（5件套含裤子） ============
    {name:"永恒套装",level:200,jobType:"byJob",
     warrior:{cap:1005980,longcoat:1042433,pants:1062285,shoes:1073629,glove:1082760},
     mage:{cap:1005981,longcoat:1042434,pants:1062286,shoes:1073630,glove:1082761},
     archer:{cap:1005982,longcoat:1042435,pants:1062287,shoes:1073631,glove:1082762},
     thief:{cap:1005983,longcoat:1042436,pants:1062288,shoes:1073632,glove:1082763},
     pirate:{cap:1005984,longcoat:1042437,pants:1062289,shoes:1073633,glove:1082764},
     conditions:{
        meso:800000000,cash:8000,
        items:[[1712001,10],[1712002,10],[1712003,10],[1712004,10],[1712005,10],[1712006,10]],
        quests:[-31416,-31318,-27811,-27916,-31206],
        killMobs:[[8880142,1]],
        equipSacrifice:[],
        specialDrops:[]}}
];

// ---- 运行时 ----
var status = -1;
var mode = null;         // "armor_upgrade" / "preview"

// ============================================================================
function start() { action(1, 0, 0); }

function action(type, mode2, selection) {
    if (type !== 1) { cm.dispose(); return; }
    status++;
    if (status === 0) showMainMenu();
    else if (status === 1) handleMenuSelect(selection);
    else if (status === 2) handleConfirm(selection);
    else cm.dispose();
}

// ============================================================================
// 主菜单
// ============================================================================
function showMainMenu() {
    var jobIdx = getJobIndex();
    if (jobIdx < 0) {
        cm.sendOk("\t\t\t\t#e#r装备升级系统#k#n\r\n\r\n当前职业不属于五大系，无法使用。");
        cm.dispose(); return;
    }

    var armorStage = getStage("armor");

    var text = "\t\t\t\t#e#r装备升级系统#k#n\r\n\r\n";
    text += "#d当前职业：#b" + JOB_NAMES[jobIdx] + "#k\r\n";

    if (armorStage >= 0) {
        text += "#d当前阶段：#b" + (armorStage + 1) + "/" + ARMOR_STAGES.length + " " + ARMOR_STAGES[armorStage].name + "#k\r\n";
    } else {
        text += "#d当前阶段：#r尚未开始#k\r\n";
    }

    text += "\r\n";

    // ---- 防具升级 ----
    if (armorStage + 1 < ARMOR_STAGES.length) {
        var nextStg = ARMOR_STAGES[armorStage + 1];
        text += "#L0##b升级 → 阶段" + (armorStage + 2) + " " + nextStg.name + " (Lv" + nextStg.level + ")#k#l\r\n";
    } else {
        text += "#d已达最高阶段(" + ARMOR_STAGES.length + "/" + ARMOR_STAGES.length + ")#k\r\n";
    }

    text += "\r\n#L300##b升级路线预览#k#l\r\n";

    cm.sendSimple(text);
}

// ============================================================================
// 菜单选择
// ============================================================================
function handleMenuSelect(selection) {
    // ---- 防具升级 ----
    if (selection === 0) {
        mode = "armor_upgrade";
        showArmorConfirm();
        return;
    }

    // ---- 预览 ----
    if (selection === 300) {
        showPreviewMenu();
        return;
    }

    cm.dispose();
}

// ============================================================================
// 防具升级确认
// ============================================================================
function showArmorConfirm() {
    var curStage = getStage("armor");
    var targetIdx = curStage + 1;
    if (targetIdx >= ARMOR_STAGES.length) { cm.sendOk("已达最高阶段。"); cm.dispose(); return; }

    var stg = ARMOR_STAGES[targetIdx];
    var jobIdx = getJobIndex();
    var targetIds = getArmorIds(targetIdx, jobIdx);
    var conds = stg.conditions;

    var text = "\t\t\t\t#e#r升级 → 阶段" + (targetIdx + 1) + " " + stg.name + "#k#n\r\n\r\n";
    text += "#e目标装备：#n\r\n" + formatPreview(targetIds) + "\r\n";
    text += "#e升级条件（" + UPGRADE_SUCCESS_RATE + "%成功率）：#n\r\n";

    text += buildConditionText(conds, targetIdx);

    cm.sendYesNo(text + "\r\n\r\n#b确定升级吗？#k");
}

// ============================================================================
// 条件文本构建
// ============================================================================
function buildConditionText(conds, targetIdx) {
    var text = "";

    // 成功率
    text += "#e成功率：#n#b" + UPGRADE_SUCCESS_RATE + "%#k\r\n\r\n";

    // 上一级套装（第2阶段开始需要）
    if (targetIdx > 0) {
        var prevStage = ARMOR_STAGES[targetIdx - 1];
        text += "#r[上一级套装]#k " + prevStage.name + "（全部放在装备栏，不要穿戴）\r\n";
    }

    // 装备献祭（按itemId）
    var sacrifices = getEquipSacrifices(conds, getJobIndex());
    if (sacrifices.length > 0) {
        text += "\r\n#e装备献祭：#n\r\n";
        for (var s = 0; s < sacrifices.length; s++) {
            var sac = sacrifices[s];
            var owned = cm.getItemQuantity(sac.itemId);
            text += (owned >= sac.count ? "#g" : "#r") + "#i" + sac.itemId + "# #t" + sac.itemId + "# × " + sac.count
                + "（已有 " + owned + "）#k\r\n";
        }
    }

    // 道具材料
    if (conds.items.length > 0) {
        text += "\r\n#e道具材料：#n\r\n";
        for (var i = 0; i < conds.items.length; i++) {
            var mat = conds.items[i];
            var owned = cm.getItemQuantity(mat[0]);
            text += (owned >= mat[1] ? "#g" : "#r") + "#i" + mat[0] + "# #t" + mat[0] + "# × " + mat[1]
                + "（已有 " + owned + "）#k\r\n";
        }
    }

    // 任务（显示名字）
    if (conds.quests.length > 0) {
        text += "\r\n#e任务要求：#n\r\n";
        for (var q = 0; q < conds.quests.length; q++) {
            var done = cm.isQuestCompleted(conds.quests[q]);
            var questName = getQuestName(conds.quests[q]);
            text += (done ? "#g[已完成]#k " : "#r[未完成]#k ") + questName + "\r\n";
        }
    }

    // 击杀指定怪物
    if (conds.killMobs.length > 0) {
        text += "\r\n#e击杀要求：#n\r\n";
        for (var k = 0; k < conds.killMobs.length; k++) {
            var mob = conds.killMobs[k];
            var killKey = KILL_KEY_PREFIX + targetIdx + "_" + mob[0];
            var killDone = parseInt(cm.getCharacterExtendValue(killKey) || "0");
            var mobName = MOB_NAMES[mob[0]] || ("怪物 " + mob[0]);
            text += (killDone >= mob[1] ? "#g" : "#r") + mobName + " × " + mob[1]
                + "（已击杀 " + killDone + "）#k\r\n";
        }
    }

    // 特殊物品（从BOSS掉落）
    if (conds.specialDrops.length > 0) {
        text += "\r\n#e特殊物品（需从BOSS掉落获得）：#n\r\n";
        for (var d = 0; d < conds.specialDrops.length; d++) {
            var drop = conds.specialDrops[d];
            var owned = cm.getItemQuantity(drop.itemId);
            var bossNames = [];
            for (var b = 0; b < drop.bossMobIds.length; b++) {
                bossNames.push(BOSS_NAMES[drop.bossMobIds[b]] || ("Boss " + drop.bossMobIds[b]));
            }
            text += (owned >= 1 ? "#g" : "#r") + "#i" + drop.itemId + "# #t" + drop.itemId + "# × 1"
                + "（已有 " + owned + "）- " + bossNames.join("/") + " 掉落" + drop.dropRate + "%#k\r\n";
        }
    }

    // 金币/点券
    text += "\r\n" + (cm.getMeso() >= conds.meso ? "#g" : "#r")
        + "金币：" + formatNum(conds.meso) + "（已有 " + formatNum(cm.getMeso()) + "）#k\r\n";
    if (conds.cash > 0) {
        var cash = cm.getPlayer().getCashShop().getCash(1);
        text += (cash >= conds.cash ? "#g" : "#r")
            + "点券：" + formatNum(conds.cash) + "（已有 " + formatNum(cash) + "）#k\r\n";
    }

    return text;
}

// ============================================================================
// 确认执行
// ============================================================================
function handleConfirm(sel) {
    if (sel !== 1) { cm.dispose(); return; }
    if (mode === "armor_upgrade") doArmorUpgrade();
    else cm.dispose();
}

function doArmorUpgrade() {
    var curStage = getStage("armor");
    var targetIdx = curStage + 1;
    if (targetIdx < 0 || targetIdx >= ARMOR_STAGES.length) {
        cm.sendOk("当前进化阶段无效，请联系管理员。"); cm.dispose(); return;
    }
    var stg = ARMOR_STAGES[targetIdx];
    var jobIdx = getJobIndex();
    var conds = stg.conditions;
    var targetIds = getArmorIds(targetIdx, jobIdx);
    var sacrifices = getEquipSacrifices(conds, jobIdx);

    // 等级
    if (cm.getPlayer().getLevel() < stg.level) {
        cm.sendOk("等级不足，需要 Lv" + stg.level); cm.dispose(); return;
    }
    // 任务
    for (var q = 0; q < conds.quests.length; q++) {
        if (!cm.isQuestCompleted(conds.quests[q])) {
            var questName = getQuestName(conds.quests[q]);
            cm.sendOk("任务 " + questName + " 未完成"); cm.dispose(); return;
        }
    }
    // 击杀指定怪物
    for (var k = 0; k < conds.killMobs.length; k++) {
        var mob = conds.killMobs[k];
        var killKey = KILL_KEY_PREFIX + targetIdx + "_" + mob[0];
        var killDone = parseInt(cm.getCharacterExtendValue(killKey) || "0");
        if (killDone < mob[1]) {
            var mobName = MOB_NAMES[mob[0]] || ("怪物 " + mob[0]);
            cm.sendOk(mobName + " 击杀数量不足：" + killDone + "/" + mob[1]); cm.dispose(); return;
        }
    }
    // 材料
    for (var i = 0; i < conds.items.length; i++) {
        if (cm.getItemQuantity(conds.items[i][0]) < conds.items[i][1]) {
            cm.sendOk("材料不足：#t" + conds.items[i][0] + "#"); cm.dispose(); return;
        }
    }
    // 装备献祭
    if (sacrifices.length > 0) {
        for (var s = 0; s < sacrifices.length; s++) {
            var sac = sacrifices[s];
            if (cm.getItemQuantity(sac.itemId) < sac.count) {
                cm.sendOk("装备献祭不足：#t" + sac.itemId + "#"); cm.dispose(); return;
            }
        }
    }
    // 特殊物品（从BOSS掉落）
    if (conds.specialDrops && conds.specialDrops.length > 0) {
        for (var d = 0; d < conds.specialDrops.length; d++) {
            var drop = conds.specialDrops[d];
            if (cm.getItemQuantity(drop.itemId) < 1) {
                cm.sendOk("特殊物品不足：#t" + drop.itemId + "#"); cm.dispose(); return;
            }
        }
    }
    // 金币/点券
    if (cm.getMeso() < conds.meso) {
        cm.sendOk("金币不足，需要 " + formatNum(conds.meso) + " 金币"); cm.dispose(); return;
    }
    var currentCash = cm.getPlayer().getCashShop().getCash(1);
    if (currentCash < conds.cash) {
        cm.sendOk("点券不足，需要 " + formatNum(conds.cash) + " 点券"); cm.dispose(); return;
    }

    // 上一级套装检查（第2阶段开始需要）
    var prevIds = [];
    if (targetIdx > 0) {
        prevIds = getArmorIds(targetIdx - 1, jobIdx);
        var inv = cm.getPlayer().getInventory(InventoryType.EQUIP);
        for (var p = 0; p < prevIds.length; p++) {
            if (!inv.findById(prevIds[p])) {
                cm.sendOk("请把" + ARMOR_STAGES[targetIdx - 1].name + "全部放在装备栏（缺少 #v" + prevIds[p] + "# #z" + prevIds[p] + "#）");
                cm.dispose(); return;
            }
        }
    }

    // 先确认全部目标装备资源存在，避免扣除后只发放部分套装。
    var ii = ItemInformationProvider.getInstance();
    var targetEquips = [];
    for (var t = 0; t < targetIds.length; t++) {
        var targetEquip = ii.getEquipById(targetIds[t]);
        if (!targetEquip) {
            cm.sendOk("目标装备资源不存在：" + targetIds[t]); cm.dispose(); return;
        }
        targetEquips.push(targetEquip);
    }

    // 上一套和装备献祭会先释放格子，只要求换装后的净空位足够。
    var releasedEquipSlots = prevIds.length;
    for (var e = 0; e < sacrifices.length; e++) releasedEquipSlots += sacrifices[e].count;
    var freeSlots = cm.getPlayer().getInventory(InventoryType.EQUIP).getNumFreeSlot();
    if (freeSlots + releasedEquipSlots < targetIds.length) {
        var missingSlots = targetIds.length - freeSlots - releasedEquipSlots;
        cm.sendOk("装备栏还需要 " + missingSlots + " 个空位"); cm.dispose(); return;
    }

    // 扣装备献祭
    if (sacrifices.length > 0) {
        for (var s = 0; s < sacrifices.length; s++) {
            var sac = sacrifices[s];
            cm.gainItem(sac.itemId, -sac.count);
        }
    }
    // 扣材料
    for (var i = 0; i < conds.items.length; i++) cm.gainItem(conds.items[i][0], -conds.items[i][1]);
    // 扣特殊物品
    if (conds.specialDrops && conds.specialDrops.length > 0) {
        for (var d = 0; d < conds.specialDrops.length; d++) {
            cm.gainItem(conds.specialDrops[d].itemId, -1);
        }
    }
    // 上一套也是进化成本，失败时不返还。
    if (targetIdx > 0) consumePrevArmor(targetIdx - 1, jobIdx);
    cm.gainMeso(-conds.meso);
    cm.getPlayer().getCashShop().gainCash(1, -conds.cash);

    // 成功率判定
    var rand = Math.random() * 100;
    if (rand >= UPGRADE_SUCCESS_RATE) {
        // 上一套已销毁，清空整条进化记录和所有击杀进度。
        resetAllKillCounts();
        cm.saveOrUpdateCharacterExtendValue(STAGE_KEY_PREFIX + "armor", "-1");
        cm.sendOk("#r升级失败！#k\r\n\r\n上一套装备、材料、献祭装备、金币和点券均已消耗。\r\n套装进化记录和全部击杀数量已清零，请从30级套装重新制作。\r\n（成功率：" + UPGRADE_SUCCESS_RATE + "%）");
        cm.dispose(); return;
    }

    // 发放新装备
    for (var j = 0; j < targetEquips.length; j++) cm.gainEquip(targetEquips[j]);
    resetKillCount(targetIdx);
    cm.saveOrUpdateCharacterExtendValue(STAGE_KEY_PREFIX + "armor", String(targetIdx));
    cm.sendOk("升级成功！\r\n\r\n#b" + stg.name + "#k\r\n" + formatPreview(targetIds));
    cm.dispose();
}

// ============================================================================
// 预览
// ============================================================================
function showPreviewMenu() {
    var jobIdx = getJobIndex();
    var text = "\t\t\t\t#e#r装备升级路线预览#k#n\r\n\r\n";

    text += "#e防具路线（" + ARMOR_STAGES.length + "阶段）：#n\r\n";
    for (var i = 0; i < ARMOR_STAGES.length; i++) {
        var ids = getArmorIds(i, jobIdx);
        text += "#bLv" + ARMOR_STAGES[i].level + " " + ARMOR_STAGES[i].name + "#k ";
        for (var j = 0; j < ids.length; j++) text += "#v" + ids[j] + "#";
        text += "\r\n";
    }

    cm.sendOk(text); cm.dispose();
}

// ============================================================================
// 工具函数
// ============================================================================
function getQuestName(questId) {
    try {
        var quest = Quest.getInstance(questId);
        if (quest && quest.getName()) {
            return quest.getName();
        }
    } catch (e) {
        // 忽略异常
    }
    return "任务 " + questId;
}

function getStage(type) {
    var stage = parseInt(cm.getCharacterExtendValue(STAGE_KEY_PREFIX + type) || "-1", 10);
    return isNaN(stage) || stage < -1 || stage >= ARMOR_STAGES.length ? -1 : stage;
}

function getJobIndex() {
    var style = Job.getJobStyleInternal(cm.getPlayer().getJob().getId(), 0);
    var niche = style.getJobNiche();
    return niche >= 1 && niche <= 5 ? niche - 1 : -1;
}

function getArmorIds(stageIdx, jobIdx) {
    var stg = ARMOR_STAGES[stageIdx];
    var jobKey = ["warrior","mage","archer","thief","pirate"][jobIdx];
    var equips;

    if (stg.jobType === "all") {
        equips = stg.equips;
    } else {
        equips = stg[jobKey];
    }

    var ids = [equips.cap, equips.longcoat];
    if (equips.pants) ids.push(equips.pants);
    ids.push(equips.shoes, equips.glove);
    return ids;
}

function getEquipSacrifices(conds, jobIdx) {
    var result = [];
    if (conds.equipSacrifice) {
        for (var i = 0; i < conds.equipSacrifice.length; i++) result.push(conds.equipSacrifice[i]);
    }
    if (conds.equipSacrificeByJob && conds.equipSacrificeByJob[jobIdx]) {
        var jobSacrifices = conds.equipSacrificeByJob[jobIdx];
        for (var j = 0; j < jobSacrifices.length; j++) result.push(jobSacrifices[j]);
    }
    return result;
}

function consumePrevArmor(prevStage, jobIdx) {
    var ids = getArmorIds(prevStage, jobIdx);
    var inv = cm.getPlayer().getInventory(InventoryType.EQUIP);
    for (var i = 0; i < ids.length; i++) {
        var item = inv.findById(ids[i]);
        if (item) InventoryManipulator.removeFromSlot(cm.getPlayer().getClient(), InventoryType.EQUIP, item.getPosition(), 1, false);
    }
}

function resetKillCount(stageIdx) {
    var stg = ARMOR_STAGES[stageIdx];
    for (var k = 0; k < stg.conditions.killMobs.length; k++) {
        var mob = stg.conditions.killMobs[k];
        var killKey = KILL_KEY_PREFIX + stageIdx + "_" + mob[0];
        cm.saveOrUpdateCharacterExtendValue(killKey, "0");
    }
}

function resetAllKillCounts() {
    for (var stageIdx = 0; stageIdx < ARMOR_STAGES.length; stageIdx++) {
        resetKillCount(stageIdx);
    }
}

function formatPreview(ids) {
    var t = "";
    for (var i = 0; i < ids.length; i++) {
        t += "#v" + ids[i] + "# #z" + ids[i] + "#";
        t += i % 2 === 1 || i === ids.length - 1 ? "\r\n" : "    ";
    }
    return t;
}

function formatNum(v) { return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

// ---- 怪物名称 ----
var MOB_NAMES = {
    1140100:"古木妖",2130103:"青蛇",3230300:"幼魔精灵",
    4230125:"石膏犬",4230102:"大幽灵",4130100:"土龙",3230100:"风独眼兽",
    6230601:"黑恐龙",6230100:"怪猫",6130208:"克鲁",7130104:"凯丁",6130209:"妙仙",
    2230103:"绿蜘蛛",3230103:"吹泡泡鱼皇",3230304:"运输机",3230400:"打鼓兔子",6230300:"红小丑",
    8140600:"骨骸鱼",8140701:"红海龟龙",8140702:"犀牛龙",8141100:"大海贼王",8141300:"乌贼怪",
    9400013:"朦胧鬼",8140101:"暗黑半人马",8140111:"恶魔绵羊",9400205:"蓝蘑菇王",
    9420530:"偷轮胎犯",9420533:"影子猎犬",9420538:"玩具飞机心疤狮",9420540:"马戏团暴力熊",
    9400542:"紫色火焰象",9400562:"邪术娃娃",
    8190004:"老骷髅龙",8200008:"后悔的守护队长",8200010:"忘却的神官",
    8800002:"扎昆",9400300:"大头头",8510000:"鱼王",9400549:"死灵骑士",9400575:"大脚",8150000:"蝙蝠魔",
    8810018:"暗黑龙王",
    8600000:"变异的蜗大牛",8600001:"变异的花蘑大菇",8600002:"变异的绿水大灵",8600003:"变异的漂漂大猪",
    8600004:"变异的提大诺",8600005:"变异的提大鲁",8600006:"变异的提古大尔",
    8610005:"正式骑士A",8610006:"正式骑士B",8610007:"正式骑士C",8610008:"正式骑士D",8610009:"正式骑士E",
    8610010:"高级骑士A",8610011:"高级骑士B",8610012:"高级骑士C",8610013:"高级骑士D",8610014:"高级骑士E",
    8880142:"露希妲"
};
