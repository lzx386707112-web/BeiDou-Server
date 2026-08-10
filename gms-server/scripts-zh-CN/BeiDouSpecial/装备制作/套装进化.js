var TITLE = "\t\t\t\t#e#r装备进阶#k#n\r\n";
var STARTER_QUEST = 600003;
var STARTER_KEY = "equipment_evolution_starter_claimed";
var FAIL_KEY_PREFIX = "equipment_evolution_fail_";
var BOSS_KEY_PREFIX = "equipment_evolution_boss_";
var SET_MATERIAL_SCALE = 1;
var SET_MESO_SCALE = 6.5;
var SET_CASH_SCALE = 6;

var STARTER_RULE = {
    theme: "基础狩猎：收集皮革、矿石和主线纪念物",
    quests: [STARTER_QUEST],
    materials: [[4000032, 30], [4000024, 30], [4010000, 10], [4001126, 3]],
    meso: 300000,
    cash: 0
};

var InventoryType = Java.type("org.gms.client.inventory.InventoryType");
var InventoryManipulator = Java.type("org.gms.client.inventory.manipulator.InventoryManipulator");
var ItemInformationProvider = Java.type("org.gms.server.ItemInformationProvider");
var Job = Java.type("org.gms.client.Job");

var JOB_NAMES = ["战士", "法师", "弓箭手", "飞侠", "海盗"];

// Shared armor is ordered as cap, longcoat, glove, shoes and cape.
var SHARED_SETS = [
    {name: "冒险岛宝石", armor: [1003242, 1052357, 1082314, 1072521, 1102294], weapons: [1302169, 1372096, 1452125, 1332144, 1482098]},
    {name: "冒险岛铂金", armor: [1003243, 1052358, 1082315, 1072522, 1102295], weapons: [1302170, 1372097, 1452126, 1332145, 1482099]},
    {name: "斯泰拉", armor: [1003723, 1052553, 1082494, 1072761, 1102502], weapons: [1302257, 1372169, 1452197, 1332215, 1482160]},
    {name: "传说冒险岛", armor: [1003364, 1052405, 1082391, 1072610, 1102322], weapons: [1302192, 1372117, 1452147, 1332168, 1482120]},
    {name: "专属紫金枫叶", armor: [1003552, 1052461, 1082433, 1072666, 1102441], weapons: [1302227, 1372139, 1452170, 1332193, 1482140]},
    {name: "风暴", armor: [1003561, 1052467, 1082438, 1072672, 1102467], weapons: [1302249, 1372162, 1452190, 1332207, 1482152]},
    {name: "终极", armor: [1003740, 1052569, 1082498, 1072768, 1102506], weapons: [1302258, 1372170, 1452198, 1332216, 1482161]},
    {name: "革命", armor: [1003946, 1052647, 1082540, 1072853, 1102612], weapons: [1302289, 1372188, 1452216, 1332238, 1482179]}
];

// Branch item order is weapon, cap, longcoat, glove, shoes and cape.
var BRANCH_SETS = {
    lion120: {name: "120级班·雷昂", items: [
        [1302193, 1003154, 1052299, 1082285, 1072471, 1102262],
        [1372119, 1003155, 1052300, 1082286, 1072472, 1102263],
        [1452149, 1003156, 1052301, 1082287, 1072473, 1102264],
        [1332170, 1003157, 1052302, 1082288, 1072474, 1102265],
        [1482122, 1003158, 1052303, 1082289, 1072475, 1102266]
    ]},
    lion125: {name: "125级班·雷昂", items: [
        [1302175, 1003290, 1052384, 1082338, 1072554, 1102312],
        [1372102, 1003291, 1052385, 1082339, 1072555, 1102313],
        [1452131, 1003292, 1052386, 1082340, 1072556, 1102314],
        [1332152, 1003293, 1052387, 1082341, 1072557, 1102315],
        [1482104, 1003294, 1052388, 1082342, 1072558, 1102316]
    ]},
    royal: {name: "皇家班·雷昂", items: [
        [1302316, 1004234, 1052804, 1082613, 1072972, 1102713],
        [1372208, 1004235, 1052805, 1082614, 1072973, 1102714],
        [1452239, 1004236, 1052806, 1082615, 1072974, 1102715],
        [1332261, 1004237, 1052807, 1082616, 1072975, 1102716],
        [1482203, 1004238, 1052808, 1082617, 1072976, 1102717]
    ]},
    empress: {name: "女皇", items: [
        [1302152, 1003172, 1052314, 1082295, 1072485, 1102275],
        [1372084, 1003173, 1052315, 1082296, 1072486, 1102276],
        [1452111, 1003174, 1052316, 1082297, 1072487, 1102277],
        [1332130, 1003175, 1052317, 1082298, 1072488, 1102278],
        [1482084, 1003176, 1052318, 1082299, 1072489, 1102279]
    ]},
    pensalir: {name: "芬撒里尔", items: [
        [1302315, 1004229, 1052799, 1082608, 1072967, 1102718],
        [1372207, 1004230, 1052800, 1082609, 1072968, 1102719],
        [1452238, 1004231, 1052801, 1082610, 1072969, 1102720],
        [1332260, 1004232, 1052802, 1082611, 1072970, 1102721],
        [1482202, 1004233, 1052803, 1082612, 1072971, 1102722]
    ]},
    sengoku: {name: "战国", items: [
        [1302229, 1003601, 1052509, 1082472, 1072711, 1102456],
        [1372141, 1003603, 1052511, 1082474, 1072713, 1102458],
        [1452172, 1003602, 1052510, 1082473, 1072712, 1102457],
        [1332195, 1003604, 1052512, 1082475, 1072714, 1102459],
        [1482142, 1003605, 1052513, 1082476, 1072715, 1102460]
    ]},
    absolab: {name: "埃苏莱布斯", items: [
        [1302333, 1004422, 1052882, 1082636, 1073030, 1102775],
        [1372222, 1004423, 1052887, 1082637, 1073032, 1102794],
        [1452252, 1004424, 1052888, 1082638, 1073033, 1102795],
        [1332274, 1004425, 1052889, 1082639, 1073034, 1102796],
        [1482216, 1004426, 1052890, 1082640, 1073035, 1102797]
    ]},
    arcane: {name: "神秘之影", items: [
        [1302343, 1004808, 1053063, 1082695, 1073158, 1102940],
        [1372228, 1004809, 1053064, 1082696, 1073159, 1102941],
        [1452257, 1004810, 1053065, 1082697, 1073160, 1102942],
        [1332279, 1004811, 1053066, 1082698, 1073161, 1102943],
        [1482221, 1004812, 1053067, 1082699, 1073162, 1102944]
    ]},
    destiny: {name: "天命/永恒", items: [
        [1302376, 1005980, 1042433, 1082760, 1073629, 1103433],
        [1372252, 1005981, 1042434, 1082761, 1073630, 1103434],
        [1452287, 1005982, 1042435, 1082762, 1073631, 1103435],
        [1332305, 1005983, 1042436, 1082763, 1073632, 1103436],
        [1482247, 1005984, 1042437, 1082764, 1073633, 1103437]
    ]},
    eternalPants: {items: [1062285, 1062286, 1062287, 1062288, 1062289]}
};

// Existing weapon-crafting targets are the canonical weapon path. Item order is
// Fafnir, Absolab, Sweetwater, Arcane and Destiny.
var WEAPON_PATHS = [
    [
        {name: "单手剑", items: [1302275, 1302333, 1302297, 1302343, 1302376]},
        {name: "单手斧", items: [1312153, 1312199, 1312173, 1312203, 1312227]},
        {name: "单手锤", items: [1322203, 1322250, 1322223, 1322255, 1322283]},
        {name: "双手剑", items: [1402196, 1402251, 1402220, 1402259, 1402295]},
        {name: "双手斧", items: [1412135, 1412177, 1412152, 1412181, 1412198]},
        {name: "双手锤", items: [1422140, 1422184, 1422158, 1422189, 1422210]},
        {name: "枪", items: [1432167, 1432214, 1432187, 1432218, 1432242]},
        {name: "矛", items: [1442223, 1442268, 1442242, 1442274, 1442301]}
    ],
    [
        {name: "短杖", items: [1372177, 1372222, 1372195, 1372228, 1372252]},
        {name: "长杖", items: [1382272, 1382259, 1382231, 1382265, 1382289]}
    ],
    [
        {name: "弓", items: [1452205, 1452252, 1452226, 1452257, 1452287]},
        {name: "弩", items: [1462193, 1462239, 1462213, 1462243, 1462270]}
    ],
    [
        {name: "短刀", items: [1332225, 1332274, 1332247, 1332279, 1332305]},
        {name: "拳套", items: [1472214, 1472261, 1472235, 1472265, 1472290]}
    ],
    [
        {name: "拳甲", items: [1482168, 1482216, 1482189, 1482221, 1482247]},
        {name: "短枪", items: [1492179, 1492231, 1492199, 1492235, 1492261]}
    ]
];

var WEAPON_STAGE_NAMES = ["法弗纳", "埃苏莱布斯", "漩涡", "神秘之影", "天命"];
var WEAPON_LEVEL_EXPAND = [2, 4, 6, 10, 15];
var WEAPON_MAX_STAR = [20, 30, 40, 50, 60];

var STEP_RULES = [
    {theme: "三色蜗牛王冠：收集三色蜗牛壳并完成基础锻造", bosses: [2220000], materials: [[4000000, 40], [4000016, 40], [4000019, 40], [4011000, 5], [4003000, 20]], meso: 200000, cash: 0, chance: 100, pity: 0},
    {theme: "野性骨架：用皮革、尖牙和龙皮加固整套装备", bosses: [9400610, 9400609], materials: [[4000021, 35], [4000020, 35], [4000030, 15], [4011001, 5], [4003000, 20]], meso: 500000, cash: 0, chance: 100, pity: 0},
    {theme: "双色珠宝：将狩猎素材与紫水晶、祖母绿镶入装备", quests: [600004], bosses: [9400613, 9400612], materials: [[4000079, 25], [4000229, 25], [4021001, 3], [4021003, 3], [4000313, 5]], meso: 800000, cash: 500, chance: 95, pity: 3},
    {theme: "四维觉醒：集齐力量、智慧、敏捷、幸运四种水晶", quests: [600005], bosses: [9400611, 9400633], materials: [[4005000, 2], [4005001, 2], [4005002, 2], [4005003, 2], [4000313, 5]], meso: 1500000, cash: 800, chance: 90, pity: 4},
    {theme: "工匠重铸：加工木材、钢铁、螺丝和黑水晶共同塑形", bosses: [3220000, 3220001], materials: [[4003001, 20], [4011001, 5], [4003000, 30], [4021008, 2]], meso: 2500000, cash: 1000, chance: 85, pity: 5},
    {theme: "深海秘炼：以歇尔夫珍珠为核心进行黑暗宝石炼成", bosses: [4220001, 5220002], materials: [[4032474, 1], [4005004, 1], [4250000, 2], [4251300, 2]], meso: 4000000, cash: 1500, chance: 80, pity: 6},
    {theme: "组队远征：取得毒物森林、玩具塔和海盗船三种凭证", bosses: [5220004, 5220001], materials: [[4001198, 1], [4001246, 1], [4032266, 1], [4021009, 1]], meso: 6000000, cash: 2000, chance: 75, pity: 7},
    {theme: "王室封印：用主线纪念物、月石和五彩水晶完成认证", quests: [600006], bosses: [5220003], materials: [[4000313, 5], [4011007, 2], [4251200, 1], [4260009, 1]], meso: 10000000, cash: 3000, chance: 70, pity: 8},
    {theme: "狮王共鸣：用四种下等属性宝石与日月精华唤醒套装", bosses: [6220000, 6220001], materials: [[4250800, 2], [4250900, 2], [4251000, 2], [4251100, 2], [4011007, 2], [4021009, 2]], meso: 15000000, cash: 5000, chance: 65, pity: 8},
    {theme: "皇家试炼：青竹武士与九尾狐资格加三种中等宝石", quests: [31180], bosses: [6090002, 7220001], materials: [[4250001, 1], [4251301, 1], [4251401, 1], [4260009, 2]], meso: 20000000, cash: 7000, chance: 60, pity: 8},
    {theme: "武陵猎证：收集肯德熊熊掌与妖怪禅师娃娃", route: "pensalir", quests: [600007], bosses: [7220000, 7220002], materials: [[4000283, 10], [4000289, 10], [4251200, 1], [4000313, 5]], meso: 25000000, cash: 8000, chance: 65, pity: 8},
    {theme: "女皇祝福：以艾利杰角尾、星石和希纳斯宝石授勋", route: "empress", quests: [600007], bosses: [8220000, 8850011], materials: [[4000073, 20], [4000074, 20], [4021009, 2], [4260009, 2]], meso: 30000000, cash: 10000, chance: 55, pity: 9},
    {theme: "时空三印：吉米拉、小吃店与阿卡伊勒共同开启高阶锻造", bosses: [8220002, 8220009, 8860000], materials: [[4260009, 3], [4250001, 2], [4251301, 2], [4011007, 2], [4021009, 2]], meso: 40000000, cash: 12000, chance: 50, pity: 9},
    {theme: "深渊合铸：大海兽与鲁塔比斯四守卫资格激活五晶核心", bosses: [8220003, 8910100, 8900100, 8920100, 8930100], materials: [[4250801, 1], [4250901, 1], [4251001, 1], [4251101, 1], [4251302, 1], [4260009, 5]], meso: 60000000, cash: 15000, chance: 45, pity: 10},
    {theme: "奥术成长：完成奥术河任务并以核心宝石和高阶宝石突破", quests: [34102, 34103, 34104, 34105], materials: [[2435719, 15], [4250002, 1], [4251302, 1], [4251401, 1]], meso: 80000000, cash: 20000, chance: 35, pity: 10},
    {theme: "神说终章：七位神说Boss的强化宝石与少量时间之石共鸣", bosses: [8870000, 8870200, 8880400, 8880200, 8645009, 8880700, 8880803], materials: [[2435719, 30], [4021010, 3], [4011007, 3], [4021009, 3], [4260009, 7]], meso: 120000000, cash: 30000, chance: 25, pity: 10}
];

var BOSS_NAMES = {
    2220000: "红蜗牛王", 9400610: "黑暗独角兽", 9400609: "印第安老斑鸠",
    9400613: "沃勒福", 9400612: "牛魔王", 9400611: "雪之猫女", 9400633: "牛魔王",
    3220000: "树妖王", 3220001: "大宇", 4220001: "歇尔夫", 5220002: "浮士德",
    5220004: "巨型蜈蚣", 5220001: "巨居蟹", 5220003: "提莫", 6220000: "多尔",
    6220001: "朱诺", 6090002: "青竹武士", 7220001: "九尾狐", 7220000: "肯德熊",
    7220002: "妖怪禅师", 8220000: "艾利杰", 8220002: "吉米拉", 8220009: "小吃店",
    8220003: "大海兽",
    8860000: "阿卡伊勒", 8850011: "希纳斯",
    8910100: "半半", 8900100: "皮埃尔", 8920100: "血腥女王", 8930100: "贝伦",
    8870000: "希拉", 8870200: "白发希拉", 8880400: "觉醒希拉", 8880200: "卡翁",
    8645009: "敦凯尔", 8880700: "守护天使绿水灵", 8880803: "监视者卡洛斯"
};

var BOSS_MAPS = {
    2220000: 104000400, 9400610: 677000003, 9400609: 677000005, 9400613: 677000009,
    9400612: 677000001, 9400611: 677000007, 9400633: 677000012, 3220000: 101030404,
    3220001: 260010201, 4220001: 230020100, 5220002: 100040105, 5220004: 251010102,
    5220001: 110040000, 5220003: 220050000, 6220000: 107000300, 6220001: 221040301,
    6090002: 800020120, 7220001: 222010310, 7220000: 250010304, 7220002: 250010504,
    8220000: 200010300, 8220002: 261030000, 8220009: 105090310, 8220003: 240040401
};

var status = -1;
var selectedMode = null;
var selectedRecipe = null;
var selectedSourceIds = null;
var availableRecipes = [];
var setRecipes = buildSetRecipes();

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        showMainMenu();
    } else if (status === 1) {
        handleMainSelection(selection);
    } else if (status === 2) {
        if (selectedMode === "starter") {
            claimStarterSet();
        } else if (selectedMode === "evolve") {
            evolveSelectedSet();
        } else if (selectedMode === "preview") {
            showPreviewPage(selection);
        } else {
            cm.dispose();
        }
    } else {
        cm.dispose();
    }
}

function showMainMenu() {
    var jobIndex = getJobIndex();
    var text = TITLE;
    if (jobIndex < 0) {
        cm.sendOk(text + "当前职业不属于战士、法师、弓箭手、飞侠或海盗系列，无法使用套装进化。");
        cm.dispose();
        return;
    }

    text += "#d当前职业：#b" + JOB_NAMES[jobIndex] + "#k\r\n";
    text += "#r整套进化要求六件装备都放在装备栏，不需要固定格子。#k\r\n\r\n";

    if (cm.getCharacterExtendValue(STARTER_KEY) !== "1") {
        var starterItems = getSetItems(SHARED_SETS[0], jobIndex);
        text += "#L0##b兑换45级冒险岛宝石整套#k\r\n";
        text += formatSetPreview(starterItems) + "\r\n";
        text += buildOwnedCostText(STARTER_RULE) + "#l\r\n";
    }

    availableRecipes = getAvailableRecipes(jobIndex);
    if (availableRecipes.length === 0) {
        text += "#d装备栏中暂未检测到可进化的完整六件套。#k\r\n";
    } else {
        text += "#e检测到以下整套进化路线：#n\r\n";
        for (var i = 0; i < availableRecipes.length; i++) {
            var match = findSourceSet(availableRecipes[i], null);
            text += "#L" + (100 + i) + "##b" + availableRecipes[i].sourceName
                + " → " + availableRecipes[i].targetName + "#k\r\n";
            text += "目标预览：" + formatSetPreview(availableRecipes[i].targetIds) + "#l\r\n";
            if (match) {
                availableRecipes[i].menuSourceIds = itemIds(match);
            }
        }
    }

    text += "\r\n#L900##d查看本职业全部装备预览#k#l\r\n";
    text += "#L999##d查看整套进化规则与风险说明#k#l";
    cm.sendSimple(text);
}

function handleMainSelection(selection) {
    if (selection === 0) {
        selectedMode = "starter";
        var starterItems = getSetItems(SHARED_SETS[0], getJobIndex());
        cm.sendYesNo(TITLE
            + "#e兑换整套装备：#n\r\n" + formatDetailedPreview(starterItems)
            + "\r\n#e需要收集：#n\r\n" + buildCostText(STARTER_RULE)
            + buildQualificationText(STARTER_RULE)
            + "\r\n确定兑换吗？");
        return;
    }
    if (selection === 900) {
        selectedMode = "preview";
        showPreviewMenu();
        return;
    }
    if (selection === 999) {
        cm.sendOk(TITLE
            + "每次提交装备栏中的完整六件套，并一次获得下一阶段整套装备。\r\n"
            + "材料数量是整套一次进化的固定总需求；金币和点券按原六个部位合计。\r\n"
            + "失败会消耗材料、金币和点券，但整套装备不会消失或降级；每次失败使下次成功率提高5%，最多提高25%，达到保底次数后下一次必定成功。\r\n"
            + "强化增量、已用卷轴次数、星级和装备标记会按对应部位继承。最终天命阶段由套服拆分为上衣和裤子，强化增量继承到上衣，裤子为干净属性。\r\n"
            + "原装备制作中的帽子、鞋子和披风可替代对应阶段的同部位装备，随整套一起进化。\r\n"
            + "Boss和任务资格永久有效，不会因尝试而消耗。\r\n\r\n"
            + "#r希纳斯、鲁塔比斯、奥术河和神说Boss地图仍有兼容风险。本菜单只检查资格，绝不会传送到这些地图。#k");
        cm.dispose();
        return;
    }

    var index = selection - 100;
    if (index < 0 || index >= availableRecipes.length) {
        cm.sendOk("无效的选择。");
        cm.dispose();
        return;
    }

    selectedMode = "evolve";
    selectedRecipe = availableRecipes[index];
    var sources = findSourceSet(selectedRecipe, selectedRecipe.menuSourceIds || null);
    if (!sources) {
        cm.sendOk("装备栏中的整套装备已经变化，请重新打开菜单。");
        cm.dispose();
        return;
    }
    selectedSourceIds = itemIds(sources);
    cm.sendYesNo(buildConfirmation(selectedRecipe, selectedSourceIds));
}

function showPreviewMenu() {
    var jobIndex = getJobIndex();
    var text = TITLE
        + "#L901##b冒险岛宝石至传说套装预览#k#l\r\n"
        + "#L902##b紫金枫叶至皇家套装预览#k#l\r\n"
        + "#L903##b高级防具路线预览#k#l\r\n\r\n#e武器路线：#n\r\n";
    var paths = WEAPON_PATHS[jobIndex];
    for (var i = 0; i < paths.length; i++) {
        text += "#L" + (910 + i) + "##b" + paths[i].name + "#k "
            + formatSetPreview(paths[i].items) + "#l\r\n";
    }
    cm.sendSimple(text);
}

function showPreviewPage(selection) {
    var jobIndex = getJobIndex();
    var text = TITLE;
    if (selection === 901) {
        text += "#e冒险岛宝石至传说套装预览#n\r\n";
        for (var i = 0; i < 4; i++) {
            text += "\r\n#b" + SHARED_SETS[i].name + "#k "
                + formatSetPreview(getSetItems(SHARED_SETS[i], jobIndex));
        }
    } else if (selection === 902) {
        text += "#e紫金枫叶至皇家套装预览#n\r\n";
        for (var s = 4; s < SHARED_SETS.length; s++) {
            text += "\r\n#b" + SHARED_SETS[s].name + "#k "
                + formatSetPreview(getSetItems(SHARED_SETS[s], jobIndex));
        }
        var earlyBranches = ["lion120", "lion125", "royal"];
        for (var j = 0; j < earlyBranches.length; j++) {
            var earlySet = BRANCH_SETS[earlyBranches[j]];
            text += "\r\n#b" + earlySet.name + "#k "
                + formatSetPreview(earlySet.items[jobIndex]);
        }
    } else if (selection === 903) {
        text += "#e高级防具路线预览#n\r\n#d武器会按所选武器路线同步进化。#k\r\n";
        var armorBranches = ["pensalir", "empress", "sengoku", "absolab", "arcane"];
        for (var k = 0; k < armorBranches.length; k++) {
            var armorSet = BRANCH_SETS[armorBranches[k]];
            text += "\r\n#b" + armorSet.name + "防具#k "
                + formatSetPreview(armorSet.items[jobIndex].slice(1));
        }
        text += "\r\n#b" + BRANCH_SETS.destiny.name + "防具#k "
            + formatSetPreview(getFinalSetItems(jobIndex, WEAPON_PATHS[jobIndex][0]).slice(1));
    } else if (selection >= 910 && selection < 910 + WEAPON_PATHS[jobIndex].length) {
        var paths = WEAPON_PATHS[jobIndex];
        var path = paths[selection - 910];
        text += "#e" + path.name + "武器路线预览#n\r\n";
        for (var p = 0; p < path.items.length; p++) {
            text += "\r\n#b" + WEAPON_STAGE_NAMES[p] + "#k  #v" + path.items[p]
                + "# #z" + path.items[p] + "#";
        }
    } else {
        text += "无效的预览选择。";
    }
    cm.sendOk(text);
    cm.dispose();
}

function claimStarterSet() {
    var jobIndex = getJobIndex();
    if (jobIndex < 0) {
        cm.sendOk("当前职业无法兑换套装。");
        cm.dispose();
        return;
    }
    if (cm.getCharacterExtendValue(STARTER_KEY) === "1") {
        cm.sendOk("这个角色已经兑换过初级整套装备。");
        cm.dispose();
        return;
    }

    var costs = copyCosts(STARTER_RULE);
    var missing = getMissingRequirements(STARTER_RULE, costs);
    if (missing.length > 0) {
        cm.sendOk("条件不足：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }

    var items = getSetItems(SHARED_SETS[0], jobIndex);
    if (cm.getPlayer().getInventory(InventoryType.EQUIP).getNumFreeSlot() < items.length) {
        cm.sendOk("装备栏至少需要 " + items.length + " 个空位。");
        cm.dispose();
        return;
    }

    deductCosts(costs);
    for (var i = 0; i < items.length; i++) {
        cm.gainItem(items[i], 1);
    }
    cm.saveOrUpdateCharacterExtendValue(STARTER_KEY, "1");
    cm.sendOk("兑换成功：\r\n" + formatDetailedPreview(items));
    cm.dispose();
}

function evolveSelectedSet() {
    var recipe = selectedRecipe;
    if (!recipe || recipe.jobIndex !== getJobIndex()) {
        cm.sendOk("进化路线已经变化，请重新打开菜单。");
        cm.dispose();
        return;
    }

    var sources = findSourceSet(recipe, selectedSourceIds);
    if (!sources) {
        cm.sendOk("装备栏中的来源整套已经变化，请重新打开菜单。");
        cm.dispose();
        return;
    }

    var costs = getSetCosts(recipe);
    var missing = getMissingRequirements(recipe.rule, costs);
    if (missing.length > 0) {
        cm.sendOk("条件不足：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }

    var inventory = cm.getPlayer().getInventory(InventoryType.EQUIP);
    if (inventory.getNumFreeSlot() + sources.length < recipe.targetIds.length) {
        cm.sendOk("装备栏空间不足。最终套服拆分阶段需要额外保留1个空位。");
        cm.dispose();
        return;
    }

    var targets = createTargetSet(recipe, sources);
    if (!targets) {
        cm.sendOk("目标装备资源不存在，已停止进化。请联系管理员核对资源。");
        cm.dispose();
        return;
    }

    deductCosts(costs);
    var failures = getFailureCount(recipe);
    var chance = getCurrentChance(recipe, failures);
    var success = chance >= 100 || Math.random() * 100 < chance;
    if (!success) {
        failures++;
        setFailureCount(recipe, failures);
        cm.sendOk("整套进化失败。六件装备没有消失或降级。\r\n下次成功率：#r"
            + getCurrentChance(recipe, failures) + "%#k");
        cm.dispose();
        return;
    }

    for (var i = 0; i < sources.length; i++) {
        InventoryManipulator.removeFromSlot(
            cm.getPlayer().getClient(), InventoryType.EQUIP, sources[i].getPosition(), 1, false
        );
    }
    for (var j = 0; j < targets.length; j++) {
        cm.gainEquip(targets[j]);
    }
    setFailureCount(recipe, 0);

    var result = "整套进化成功：#b" + recipe.targetName + "#k\r\n"
        + formatDetailedPreview(recipe.targetIds);
    if (recipe.targetIds.length === 7) {
        result += "\r\n强化增量继承到永恒上衣；永恒裤子为干净基础属性。";
    }
    cm.sendOk(result);
    cm.dispose();
}

function createTargetSet(recipe, sources) {
    var ii = ItemInformationProvider.getInstance();
    var targets = [];
    for (var i = 0; i < recipe.targetIds.length; i++) {
        var target = ii.getEquipById(recipe.targetIds[i]);
        if (!target) {
            return null;
        }

        var sourceIndex = recipe.inheritFrom[i];
        if (sourceIndex >= 0) {
            var source = sources[sourceIndex];
            var sourceTemplate = ii.getEquipById(source.getItemId());
            if (!sourceTemplate) {
                return null;
            }
            inheritEquipment(source, sourceTemplate, target, i === 0 ? recipe : null);
        }
        targets.push(target);
    }
    return targets;
}

function inheritEquipment(source, sourceTemplate, target, recipe) {
    var statNames = ["Str", "Dex", "Int", "Luk", "Hp", "Mp", "Watk", "Matk", "Wdef", "Mdef", "Acc", "Avoid", "Hands", "Speed", "Jump", "Vicious"];
    for (var i = 0; i < statNames.length; i++) {
        var name = statNames[i];
        var delta = source["get" + name]() - sourceTemplate["get" + name]();
        target["set" + name](clampShort(target["get" + name]() + delta));
    }

    var targetLevelExpand = Math.max(source.getLevelExpand(), recipe && recipe.levelExpand || 0);
    var sourceBaseSlots = sourceTemplate.getUpgradeSlots() + source.getLevelExpand();
    var usedSlots = Math.max(0, sourceBaseSlots - source.getUpgradeSlots());
    var targetBaseSlots = target.getUpgradeSlots() + targetLevelExpand;
    target.setLevelExpand(targetLevelExpand);
    target.setUpgradeSlots(Math.max(0, targetBaseSlots - usedSlots));
    target.setLevel(Math.min(source.getLevel(), targetBaseSlots));
    target.setItemLevel(source.getItemLevel());
    target.setItemExp(source.getItemExp());
    target.setOwner(source.getOwner());
    target.setFlag(source.getFlag());
    target.setExpiration(source.getExpiration());
    target.setGiftFrom(source.getGiftFrom());
    target.setUpgradeHistory(source.getUpgradeHistory());
    target.setChaosHistory(source.getChaosHistory());
    target.setAbsorbHistory(source.getAbsorbHistory());
    target.setCombinationType(source.getCombinationType());
    target.setExpandAttribute1(source.getExpandAttribute1());
    target.setExpandAttribute2(source.getExpandAttribute2());
    target.setExpandAttribute3(source.getExpandAttribute3());
    target.setExpandAttribute4(source.getExpandAttribute4());
    target.setMaxStar(Math.max(source.getMaxStar(), recipe && recipe.maxStar || 0));
    target.setStarLevel(source.getStarLevel());
    target.setStarCount(source.getStarCount());
    target.setUpgradeResetCount(source.getUpgradeResetCount());
    target.setUpgradeReturn(source.getUpgradeReturn());
}

function buildConfirmation(recipe, sourceIds) {
    var failures = getFailureCount(recipe);
    var costs = getSetCosts(recipe);
    var text = TITLE
        + "#e来源整套：" + recipe.sourceName + "#n\r\n" + formatDetailedPreview(sourceIds)
        + "\r\n#e目标整套：" + recipe.targetName + "#n\r\n" + formatDetailedPreview(recipe.targetIds)
        + "\r\n#e整套消耗：#n\r\n" + buildCostText(costs)
        + "当前成功率：#r" + getCurrentChance(recipe, failures) + "%#k";
    if (recipe.rule.pity > 0) {
        text += "（已失败 " + failures + "/" + recipe.rule.pity + " 次）";
    }
    text += "\r\n" + buildQualificationText(recipe.rule);
    return text;
}

function buildQualificationText(rule) {
    var text = "#d永久资格：#k\r\n";
    var hasQualification = false;
    var quests = rule.quests || [];
    for (var i = 0; i < quests.length; i++) {
        hasQualification = true;
        text += qualificationLine(cm.isQuestCompleted(quests[i]), "任务 " + quests[i]) + "\r\n";
    }
    var bosses = rule.bosses || [];
    for (var j = 0; j < bosses.length; j++) {
        hasQualification = true;
        text += qualificationLine(hasBossClear(bosses[j]), getBossLabel(bosses[j])) + "\r\n";
    }
    if (!hasQualification) {
        text += "无额外任务或Boss要求。\r\n";
    }
    if (bosses.length > 0) {
        text += "#r本菜单只检查击杀资格，不提供地图传送。#k\r\n";
    }
    return text;
}

function qualificationLine(completed, label) {
    return (completed ? "#g[已完成]#k " : "#r[未完成]#k ") + label;
}

function getMissingRequirements(rule, costs) {
    var missing = [];
    var quests = rule.quests || [];
    for (var i = 0; i < quests.length; i++) {
        if (!cm.isQuestCompleted(quests[i])) {
            missing.push("任务 " + quests[i] + " 未完成");
        }
    }
    var bosses = rule.bosses || [];
    for (var j = 0; j < bosses.length; j++) {
        if (!hasBossClear(bosses[j])) {
            missing.push(getBossLabel(bosses[j]) + " 击杀资格未完成");
        }
    }
    for (var k = 0; k < costs.materials.length; k++) {
        var material = costs.materials[k];
        var owned = cm.getItemQuantity(material[0]);
        if (owned < material[1]) {
            missing.push("#t" + material[0] + "# 缺少 " + (material[1] - owned) + " 个");
        }
    }
    if (cm.getMeso() < costs.meso) {
        missing.push("金币不足，缺少 " + formatNumber(costs.meso - cm.getMeso()));
    }
    var cash = cm.getPlayer().getCashShop().getCash(1);
    if (cash < costs.cash) {
        missing.push("点券不足，缺少 " + formatNumber(costs.cash - cash));
    }
    return missing;
}

function deductCosts(costs) {
    for (var i = 0; i < costs.materials.length; i++) {
        cm.gainItem(costs.materials[i][0], -costs.materials[i][1]);
    }
    if (costs.meso > 0) {
        cm.gainMeso(-costs.meso);
    }
    if (costs.cash > 0) {
        cm.getPlayer().getCashShop().gainCash(1, -costs.cash);
    }
}

function copyCosts(rule) {
    var materials = [];
    for (var i = 0; i < rule.materials.length; i++) {
        materials.push([rule.materials[i][0], rule.materials[i][1]]);
    }
    return {materials: materials, meso: rule.meso, cash: rule.cash};
}

function getSetCosts(recipe) {
    var materials = [];
    for (var i = 0; i < recipe.rule.materials.length; i++) {
        materials.push([
            recipe.rule.materials[i][0],
            Math.ceil(recipe.rule.materials[i][1] * SET_MATERIAL_SCALE)
        ]);
    }
    return {
        materials: materials,
        meso: Math.ceil(recipe.rule.meso * SET_MESO_SCALE),
        cash: Math.ceil(recipe.rule.cash * SET_CASH_SCALE)
    };
}

function buildCostText(costs) {
    var text = "";
    for (var i = 0; i < costs.materials.length; i++) {
        text += "#i" + costs.materials[i][0] + "# #t" + costs.materials[i][0]
            + "# x " + costs.materials[i][1] + "\r\n";
    }
    text += "金币：" + formatNumber(costs.meso) + "\r\n";
    text += "点券：" + formatNumber(costs.cash) + "\r\n";
    return text;
}

function buildOwnedCostText(rule) {
    var costs = copyCosts(rule);
    var text = "";
    for (var i = 0; i < costs.materials.length; i++) {
        text += "#i" + costs.materials[i][0] + "# x " + costs.materials[i][1]
            + "（已有 " + cm.getItemQuantity(costs.materials[i][0]) + "） ";
    }
    text += "金币 " + formatNumber(costs.meso) + "\r\n";
    return text;
}

function getFailureCount(recipe) {
    return parseInt(cm.getCharacterExtendValue(getFailureKey(recipe)) || "0", 10) || 0;
}

function setFailureCount(recipe, value) {
    cm.saveOrUpdateCharacterExtendValue(getFailureKey(recipe), String(value));
}

function getFailureKey(recipe) {
    return FAIL_KEY_PREFIX + recipe.sourceOptions[0][0] + "_" + recipe.route;
}

function getCurrentChance(recipe, failures) {
    if (recipe.rule.pity > 0 && failures >= recipe.rule.pity) {
        return 100;
    }
    return Math.min(100, recipe.rule.chance + Math.min(25, failures * 5));
}

function hasBossClear(mobId) {
    return cm.getCharacterExtendValue(BOSS_KEY_PREFIX + mobId) === "1";
}

function getBossLabel(mobId) {
    var label = BOSS_NAMES[mobId] || ("Boss " + mobId);
    return BOSS_MAPS[mobId] ? label + "（#m" + BOSS_MAPS[mobId] + "#）" : label;
}

function getAvailableRecipes(jobIndex) {
    var result = [];
    for (var i = 0; i < setRecipes.length; i++) {
        if (setRecipes[i].jobIndex === jobIndex && findSourceSet(setRecipes[i], null)) {
            result.push(setRecipes[i]);
        }
    }
    return result;
}

function findSourceSet(recipe, preferredIds) {
    var inventory = cm.getPlayer().getInventory(InventoryType.EQUIP);
    var sources = [];
    for (var slot = 0; slot < recipe.sourceOptions.length; slot++) {
        var options = preferredIds ? [preferredIds[slot]] : recipe.sourceOptions[slot];
        var found = null;
        for (var option = 0; option < options.length; option++) {
            found = inventory.findById(options[option]);
            if (found) {
                break;
            }
        }
        if (!found) {
            return null;
        }
        sources.push(found);
    }
    return sources;
}

function itemIds(items) {
    var ids = [];
    for (var i = 0; i < items.length; i++) {
        ids.push(items[i].getItemId());
    }
    return ids;
}

function getJobIndex() {
    var style = Job.getJobStyleInternal(cm.getPlayer().getJob().getId(), 0);
    var niche = style.getJobNiche();
    return niche >= 1 && niche <= 5 ? niche - 1 : -1;
}

function buildSetRecipes() {
    var result = [];
    for (var job = 0; job < 5; job++) {
        for (var shared = 0; shared < SHARED_SETS.length - 1; shared++) {
            addFullSetRecipe(
                result,
                getSetItems(SHARED_SETS[shared], job), null,
                getSetItems(SHARED_SETS[shared + 1], job),
                job, STEP_RULES[shared], SHARED_SETS[shared].name,
                SHARED_SETS[shared + 1].name, "early_" + shared, null, null
            );
        }

        addFullSetRecipe(
            result,
            getSetItems(SHARED_SETS[7], job), null,
            BRANCH_SETS.lion120.items[job],
            job, STEP_RULES[7], SHARED_SETS[7].name,
            BRANCH_SETS.lion120.name, "lion120", null, null
        );
        addFullSetRecipe(
            result,
            BRANCH_SETS.lion120.items[job], "lion120",
            BRANCH_SETS.lion125.items[job],
            job, STEP_RULES[8], BRANCH_SETS.lion120.name,
            BRANCH_SETS.lion125.name, "lion125", null, null
        );
        addFullSetRecipe(
            result,
            BRANCH_SETS.lion125.items[job], "lion125",
            BRANCH_SETS.royal.items[job],
            job, STEP_RULES[9], BRANCH_SETS.lion125.name,
            BRANCH_SETS.royal.name, "royal", null, null
        );

        var paths = WEAPON_PATHS[job];
        for (var pathIndex = 0; pathIndex < paths.length; pathIndex++) {
            var path = paths[pathIndex];
            var route = "weapon_" + path.items[0];
            var royal = BRANCH_SETS.royal.items[job];
            var fafnirPensalir = combineWeaponAndArmor(path.items[0], BRANCH_SETS.pensalir.items[job]);
            var fafnirEmpress = combineWeaponAndArmor(path.items[0], BRANCH_SETS.empress.items[job]);
            var absolabSengoku = combineWeaponAndArmor(path.items[1], BRANCH_SETS.sengoku.items[job]);
            var sweetwaterAbsolab = combineWeaponAndArmor(path.items[2], BRANCH_SETS.absolab.items[job]);
            var arcaneSet = combineWeaponAndArmor(path.items[3], BRANCH_SETS.arcane.items[job]);
            var destinySet = getFinalSetItems(job, path);

            addFullSetRecipe(
                result, royal, "royal", fafnirPensalir,
                job, STEP_RULES[10], BRANCH_SETS.royal.name,
                "法弗纳" + path.name + " + " + BRANCH_SETS.pensalir.name + "防具",
                route + "_pensalir", WEAPON_LEVEL_EXPAND[0], WEAPON_MAX_STAR[0]
            );
            addFullSetRecipe(
                result, royal, "royal", fafnirEmpress,
                job, STEP_RULES[11], BRANCH_SETS.royal.name,
                "法弗纳" + path.name + " + " + BRANCH_SETS.empress.name + "防具",
                route + "_empress", WEAPON_LEVEL_EXPAND[0], WEAPON_MAX_STAR[0]
            );
            addFullSetRecipe(
                result, fafnirPensalir, null, absolabSengoku,
                job, STEP_RULES[12], "法弗纳" + path.name + " + " + BRANCH_SETS.pensalir.name + "防具",
                "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                route + "_pensalir", WEAPON_LEVEL_EXPAND[1], WEAPON_MAX_STAR[1]
            );
            addFullSetRecipe(
                result, fafnirEmpress, null, absolabSengoku,
                job, STEP_RULES[12], "法弗纳" + path.name + " + " + BRANCH_SETS.empress.name + "防具",
                "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                route + "_empress", WEAPON_LEVEL_EXPAND[1], WEAPON_MAX_STAR[1]
            );
            addFullSetRecipe(
                result, absolabSengoku, "sengoku", sweetwaterAbsolab,
                job, STEP_RULES[13], "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                "漩涡" + path.name + " + " + BRANCH_SETS.absolab.name + "防具",
                route + "_main", WEAPON_LEVEL_EXPAND[2], WEAPON_MAX_STAR[2]
            );
            addFullSetRecipe(
                result, sweetwaterAbsolab, null, arcaneSet,
                job, STEP_RULES[14], "漩涡" + path.name + " + " + BRANCH_SETS.absolab.name + "防具",
                "神秘之影" + path.name + "整套",
                route + "_arcane", WEAPON_LEVEL_EXPAND[3], WEAPON_MAX_STAR[3]
            );
            addFullSetRecipe(
                result, arcaneSet, null, destinySet,
                job, STEP_RULES[15], "神秘之影" + path.name + "整套",
                BRANCH_SETS.destiny.name + path.name + "整套",
                route + "_destiny", WEAPON_LEVEL_EXPAND[4], WEAPON_MAX_STAR[4]
            );
        }
    }
    return result;
}

function addFullSetRecipe(result, sourceItems, sourceStage, targetItems, jobIndex, rule,
                          sourceName, targetName, route, levelExpand, maxStar) {
    result.push({
        sourceOptions: getSourceOptions(sourceItems, sourceStage, jobIndex),
        targetIds: targetItems.slice(0),
        inheritFrom: targetItems.length === 7 ? [0, 1, 2, -1, 3, 4, 5] : [0, 1, 2, 3, 4, 5],
        jobIndex: jobIndex,
        rule: rule,
        sourceName: sourceName,
        targetName: targetName,
        route: route,
        levelExpand: levelExpand || 0,
        maxStar: maxStar || 0
    });
}

function getSourceOptions(items, stage, jobIndex) {
    var options = [];
    for (var i = 0; i < items.length; i++) {
        options.push([items[i]]);
    }

    if (stage === "lion120") {
        options[4].push(1072239, 1072344);
    } else if (stage === "lion125") {
        options[4].push(1072732);
        options[5].push(1102471 + jobIndex);
    } else if (stage === "royal") {
        options[1].push(1004637);
        options[4].push(1072737);
        options[5].push(1102476 + jobIndex);
    } else if (stage === "sengoku") {
        options[1].push(1003621);
        options[4].push(1072743);
        options[5].push(1102481 + jobIndex);
    }
    return options;
}

function combineWeaponAndArmor(weaponId, setItems) {
    return [weaponId].concat(setItems.slice(1));
}

function getFinalSetItems(jobIndex, weaponPath) {
    return [
        weaponPath.items[4],
        BRANCH_SETS.destiny.items[jobIndex][1],
        BRANCH_SETS.destiny.items[jobIndex][2],
        BRANCH_SETS.eternalPants.items[jobIndex],
        BRANCH_SETS.destiny.items[jobIndex][3],
        BRANCH_SETS.destiny.items[jobIndex][4],
        BRANCH_SETS.destiny.items[jobIndex][5]
    ];
}

function getSetItems(set, jobIndex) {
    return [set.weapons[jobIndex], set.armor[0], set.armor[1], set.armor[2], set.armor[3], set.armor[4]];
}

function formatSetPreview(items) {
    var text = "";
    for (var i = 0; i < items.length; i++) {
        text += "#v" + items[i] + "#";
    }
    return text;
}

function formatDetailedPreview(items) {
    var text = "";
    for (var i = 0; i < items.length; i++) {
        text += "#v" + items[i] + "# #z" + items[i] + "#";
        text += i % 2 === 1 || i === items.length - 1 ? "\r\n" : "    ";
    }
    return text;
}

function clampShort(value) {
    return Math.max(-32768, Math.min(32767, value));
}

function formatNumber(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
