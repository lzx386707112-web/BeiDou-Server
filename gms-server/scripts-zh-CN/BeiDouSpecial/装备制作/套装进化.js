// ============================================================================
// 装备进阶（套装进化）NPC 脚本
// ----------------------------------------------------------------------------
// 功能：把装备栏中的「完整六件套」一次性进化为下一阶段的整套装备。
// 流程：初始套兑换 → 17 个进化阶段（共享套 7 段 + 班·雷昂/皇家 3 段 + 武器路线 7 段）。
//
// 数据修改重点（你想改材料主要看这里）：
//   1) STARTER_RULE        —— 初始套（45 级冒险岛宝石）的兑换条件
//   2) STEP_RULES          —— 17 个进化阶段的材料/Boss/金币/点券/成功率
//   3) SET_MATERIAL_SCALE  —— 材料倍率（默认 1，即材料数量不变）
//      SET_MESO_SCALE      —— 金币倍率（默认 6.5）
//      SET_CASH_SCALE      —— 点券倍率（默认 6）
//      实际扣费在 getSetCosts() 里计算：材料不变，金币×6.5、点券×6 后向上取整。
// ============================================================================

// 标题（\t 用于居中缩进，#e#r 加红描边，#k#n 结束）
var TITLE = "\t\t\t\t#e#r装备进阶#k#n\r\n";


// 角色已领取初始套的存档键（永久一次性）
var STARTER_KEY = "equipment_evolution_starter_claimed";
// 失败次数存档键前缀（后缀 = 来源首项 id + 路线）
var FAIL_KEY_PREFIX = "equipment_evolution_fail_";
// Boss 击杀资格存档键前缀（后缀 = mobId），仅检查不消耗
var BOSS_KEY_PREFIX = "equipment_evolution_boss_";

// —— 整套进化扣费倍率（改材料整体难度时调这里）——
var SET_MATERIAL_SCALE = 1;   // 材料数量倍率（1 表示原样）
var SET_MESO_SCALE = 6.5;     // 金币倍率
var SET_CASH_SCALE = 6;       // 点券倍率

// ----------------------------------------------------------------------------
// 初始套：永久一次性兑换 45 级「冒险岛宝石」整套
//   materials: [[道具id, 数量], ...]
//   meso/cash: 原值（初始套不走倍率，直接 copyCosts）
// ----------------------------------------------------------------------------
var STARTER_RULE = {
    theme: "基础狩猎：收集皮革、矿石和主线纪念物",
    quests: [2013, 2034],  // 需先完成主线任务
    materials: [
        [4000032, 300],   // 鳄鱼皮
        [4000024, 300],   // 火野猪尖牙
        [4010000, 100],   // 青铜母矿
        [4000008, 100]      // 道符
        [4000009, 100]      // 蓝蘑菇盖
        [4000025, 100]      // 黑石块
        [4000041, 500]      // 巫婆的试验用青蛙
        [4000013, 100]      // 风独眼兽之尾
        [4000010, 100]      // 绿水灵珠
        [4000017, 100]      // 猪头
    ],
    meso: 3000000,
    cash: 6000
};

// Java 类型引用
var InventoryType = Java.type("org.gms.client.inventory.InventoryType");
var InventoryManipulator = Java.type("org.gms.client.inventory.manipulator.InventoryManipulator");
var ItemInformationProvider = Java.type("org.gms.server.ItemInformationProvider");
var Job = Java.type("org.gms.client.Job");

// 职业顺序：索引 0~4 分别对应战士/法师/弓箭手/飞侠/海盗
var JOB_NAMES = ["战士", "法师", "弓箭手", "飞侠", "海盗"];

// ----------------------------------------------------------------------------
// 共享套装（全职业通用的防具+武器套）。
// 顺序固定为：cap(帽子) / longcoat(上衣) / glove(手套) / shoes(鞋) / cape(披风)
//   armor : 五个防具部位 id
//   weapons: 五个职业(战/法/弓/飞/海)对应的武器 id
// SHARED_SETS[0..7] 之间的进化使用 STEP_RULES[0..6] + 革命→lion120(STEP_RULES[7])
// ----------------------------------------------------------------------------
var SHARED_SETS = [
    {name: "冒险岛宝石", armor: [1003242, 1052357, 1082314, 1072521, 1102294], weapons: [1302169, 1372096, 1452125, 1332144, 1482098]},
    {name: "冒险岛铂金", armor: [1003243, 1052358, 1082315, 1072522, 1102295], weapons: [1302170, 1372097, 1452126, 1332145, 1482099]},
    {name: "斯泰拉",     armor: [1003723, 1052553, 1082494, 1072761, 1102502], weapons: [1302257, 1372169, 1452197, 1332215, 1482160]},
    {name: "传说冒险岛", armor: [1003364, 1052405, 1082391, 1072610, 1102322], weapons: [1302192, 1372117, 1452147, 1332168, 1482120]},
    {name: "专属紫金枫叶", armor: [1003552, 1052461, 1082433, 1072666, 1102441], weapons: [1302227, 1372139, 1452170, 1332193, 1482140]},
    {name: "风暴",       armor: [1003561, 1052467, 1082438, 1072672, 1102467], weapons: [1302249, 1372162, 1452190, 1332207, 1482152]},
    {name: "终极",       armor: [1003740, 1052569, 1082498, 1072768, 1102506], weapons: [1302258, 1372170, 1452198, 1332216, 1482161]},
    {name: "革命",       armor: [1003946, 1052647, 1082540, 1072853, 1102612], weapons: [1302289, 1372188, 1452216, 1332238, 1482179]}
];

// ----------------------------------------------------------------------------
// 分支套装（按职业拆分的武器+防具）。
// 每个分支的 items 是「5 个职业」各自的六件套 [武器, 帽, 上衣, 手套, 鞋, 披风]
// ----------------------------------------------------------------------------
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

// ----------------------------------------------------------------------------
// 混合套：用「至尊不速之客」填补外星人套缺失的武器与第六件（腰带代替披风）。
//   armor: 五个防具部位（不含武器、不含披风）
//   weapons: 每个职业一组可选武器（数组里再按武器细分）
// ----------------------------------------------------------------------------
var VISITOR_ALIEN_SET = {
    name: "至尊不速之客·外星人",
    armor: [1003540, 1052460, 1082432, 1072664, 1132040],
    weapons: [
        [1302147, 1312062, 1322090, 1402090, 1412062, 1422063, 1432081, 1442111],
        [1372078, 1382099],
        [1452106, 1462091],
        [1332120, 1472117],
        [1482079, 1492079]
    ]
};
// 混合套第 6 件是不速之客腰带：皇家斗篷的强化先继承到腰带，下一阶段再由腰带继承回新斗篷
var VISITOR_ALIEN_SLOT_NOTE = "混合套第6件是不速之客腰带：皇家斗篷的强化会继承到腰带，下一阶段再由腰带继承回新斗篷。";

// ----------------------------------------------------------------------------
// 武器路线：每条武器（按职业组织）从法弗纳→埃苏莱布斯→漩涡→神秘之影→天命 五段。
//   items 顺序固定：法弗纳 / 埃苏莱布斯 / 漩涡 / 神秘之影 / 天命
// ----------------------------------------------------------------------------
var WEAPON_PATHS = [
    [
        {name: "单手剑", items: [1302275, 1302333, 1302297, 1302343, 1302376]},
        {name: "单手斧", items: [1312153, 1312199, 1312173, 1312203, 1312227]},
        {name: "单手锤", items: [1322203, 1322250, 1322223, 1322255, 1322283]},
        {name: "双手剑", items: [1402196, 1402251, 1402220, 1402259, 1402295]},
        {name: "双手斧", items: [1412135, 1412177, 1412152, 1412181, 1412198]},
        {name: "双手锤", items: [1422140, 1422184, 1422158, 1422189, 1422210]},
        {name: "枪",     items: [1432167, 1432214, 1432187, 1432218, 1432242]},
        {name: "矛",     items: [1442223, 1442268, 1442242, 1442274, 1442301]}
    ],
    [
        {name: "短杖", items: [1372177, 1372222, 1372195, 1372228, 1372252]},
        {name: "长杖", items: [1382272, 1382259, 1382231, 1382265, 1382289]}
    ],
    [
        {name: "弓",   items: [1452205, 1452252, 1452226, 1452257, 1452287]},
        {name: "弩",   items: [1462193, 1462239, 1462213, 1462243, 1462270]}
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
var WEAPON_LEVEL_EXPAND = [2, 4, 6, 10, 15];   // 各武器阶段追加的可强化等级
var WEAPON_MAX_STAR = [20, 30, 40, 50, 60];    // 各武器阶段最大星星数

// ----------------------------------------------------------------------------
// ★ 17 个进化阶段的材料/条件定义（你想改材料主要改这里）★
// 每个 rule 的字段含义：
//   theme   : 阶段玩法描述（仅展示用）
//   quests  : 需完成的主线任务 id 列表（永久资格，不消耗）
//   bosses  : 需击杀的 Boss(mobId) 列表（永久资格，不消耗）
//   materials: [[道具id, 数量], ...]  —— 实际数量 = 此值（SET_MATERIAL_SCALE=1）
//   meso    : 金币原值（实际 = ceil(meso × SET_MESO_SCALE)）
//   cash    : 点券原值（实际 = ceil(cash × SET_CASH_SCALE)）
//   chance  : 基础成功率(%)
//   pity    : 保底次数（失败达到该次数后下一次必成功）
// 注：route 字段仅用于内部区分同名 rule 复用的不同分支，普通改材料无需动它。
// 下方每个条目都标注了「对应进化（来源 → 目标）」方便定位。
// ----------------------------------------------------------------------------
var STEP_RULES = [
    // 级0  三色蜗牛王冠：冒险岛宝石 → 冒险岛铂金
    {theme: "三色蜗牛王冠：收集三色蜗牛壳并完成基础锻造",
     quests: [2878,2039,2043,2048], bosses: [2220000],
     materials: [
         [4000000, 400],   // 蓝色蜗牛壳
         [4000016, 400],   // 红色蜗牛壳
         [4000019, 400],   // 绿色蜗牛壳
         [4000206, 100],   //  肋骨
         [4000185, 100],   //  寒冰背部骨
         [4000027, 100],   //  怪猫的眼
         [4000028, 100],   //  月牙牛魔王的角
         [4021007, 50],    // 钻石
         [4003000, 100]    // 螺丝钉
         [4031162, 100]    // 旧木板
     ],
     meso: 20000000, cash: 7000, chance: 90, pity: 0},

    // 级1  野性骨架：冒险岛铂金 → 斯泰拉
    {theme: "野性骨架：用皮革、尖牙和龙皮加固整套装备",
     quests: [2897,2028],bosses: [9400610, 9400609],
     materials: [
         [1302015, 1],   // 英雄的战剑
         [1032000, 1],   // 锤耳环
         [1332023, 1],   // 锤耳环
         [1312042, 1],   // 锤耳环
         [4000021, 350],   // 动物皮
         [4000020, 350],   // 野猪尖牙
         [4000030, 150],   // 龙皮
         [4011001, 100],    // 钢铁
         [4010004, 100],    // 钢铁
         [4000009, 100],    // 钢铁
         [4010007, 100],    // 钢铁
         [4003000, 150]    // 螺丝钉
         [4000208, 150]    // 螺丝钉
     ],
     meso: 50000000, cash:8000, chance: 85, pity: 0},

    // 级2  双色珠宝：斯泰拉 → 传说冒险岛（任务600004）
    {theme: "双色珠宝：将狩猎素材与紫水晶、祖母绿镶入装备",
     bosses: [9400613, 9400612],
     materials: [
         [1002006, 1],   // 猎犬的尖牙
         [1002012, 1],   // 猎犬的尖牙
         [4000079, 250],   // 猎犬的尖牙
         [4000229, 250],   // 黑暗莱西毛球
         [4021001, 300],    // 紫水晶
         [4021003, 300],    // 祖母绿
         [4000313, 5]     // 黄金枫叶
         [4030000, 10]     // 黄金枫叶
         [4030001, 10]     // 黄金枫叶
         [4030010, 10]     // 黄金枫叶
         [4030011, 10]     // 黄金枫叶
         [4030013, 10]     // 黄金枫叶
         [4030014, 10]     // 黄金枫叶
         [4030015, 10]     // 黄金枫叶
         [4030016, 10]     // 黄金枫叶
         [4030009, 1]     // 黄金枫叶
     ],
     meso: 80000000, cash: 9000, chance: 80, pity: 3},

    // 级3  四维觉醒：传说冒险岛 → 专属紫金枫叶（任务600005）
    {theme: "四维觉醒：集齐力量、智慧、敏捷、幸运四种水晶",
     quests: [2152,2206],bosses: [9400611, 9400633,9400120],
     materials: [
         [1082002, 1],    // 力量水晶
         [1092008, 1],    // 力量水晶
         [1092004, 1],    // 力量水晶
         [1102003, 1],    // 力量水晶
         [1122007, 1],    // 力量水晶
         [4030012, 300],    // 力量水晶
         [4005000, 200],    // 力量水晶
         [4005001, 200],    // 智慧水晶
         [4005002, 200],    // 敏捷水晶
         [4005003, 200],    // 幸运水晶
         [4000313, 20]     // 黄金枫叶
         [4001126, 10]     // 黄金枫叶
     ],
     meso: 90000000, cash: 10000, chance: 80, pity: 4},

    // 级4  工匠重铸：专属紫金枫叶 → 风暴
    {theme: "工匠重铸：加工木材、钢铁、螺丝和黑水晶共同塑形",
     quests: [3209,3202,3220], bosses: [3220000, 3220001],
     materials: [
         [4003001, 60],   // 木材
         [4011001, 100],    // 钢铁
         [4003000, 50],   // 螺丝钉
         [4021008, 200]     // 黑水晶
         [4000057, 200]     // 黑水晶
         [4000063, 200]     // 黑水晶
         [4000069, 200]     // 黑水晶
         [4000074, 200]     // 黑水晶
         [4000079, 200]     // 黑水晶
         [4000082, 30]     // 黑水晶
         [4000099, 100]     // 黑水晶
         [4000103, 200]     // 黑水晶
         [4000100, 200]     // 黑水晶
         [4000123, 200]     // 黑水晶
     ],
     meso: 100000000, cash: 10000, chance: 80, pity: 5},

    // 级5  深海秘炼：风暴 → 终极
    {theme: "深海秘炼：以歇尔夫珍珠为核心进行黑暗宝石炼成",
     quests: [3497,9412,3905,3082],bosses: [4220001, 5220002],
     materials: [
         [4032474, 10],    // 歇尔夫的珍珠
         [4005004, 100],    // 黑暗水晶
         [4250000, 200],    // 苔藓蜗牛
         [4251300, 200]     // 下等黑水晶
         [4000157, 20]     // 下等黑水晶
         [4000166, 100]     // 下等黑水晶
         [4000167, 100]     // 下等黑水晶
         [4000165, 100]     // 下等黑水晶
         [4000164, 100]     // 下等黑水晶
         [4000163, 100]     // 下等黑水晶
         [4000162, 100]     // 下等黑水晶
         [4000161, 100]     // 下等黑水晶
         [4000160, 100]     // 下等黑水晶
         [4000155, 100]     // 下等黑水晶
     ],
     meso: 100000000, cash:10000, chance: 75, pity: 6},

    // 级6  组队远征：终极 → 革命
    {theme: "组队远征：取得毒物森林、玩具塔和海盗船三种凭证",
     quests: [3802,3808,3811,3905，3920],bosses: [5220004, 5220001],
     materials: [
         [4001198, 1],    // 阿尔泰碎片
         [4001246, 1],    // 温暖的阳光
         [4032266, 1],    // 耀眼的阳光
         [4021009, 10]     // 星石
         [4000168, 100]     // 星石
         [4000169, 100]     // 星石
         [4000170, 100]     // 星石
         [4000171, 100]     // 星石
         [4000172, 100]     // 星石
         [4000173, 100]     // 星石
         [4000178, 100]     // 星石
         [4000187, 100]     // 星石
         [4000188, 100]     // 星石
         [4000189, 100]     // 星石
         [4000190, 100]     // 星石
         [4000193, 100]     // 星石
         [4000192, 100]     // 星石
         [4000191, 100]     // 星石
     ],
     meso: 100000000, cash: 10000, chance: 70, pity: 7},

    // 级7  王室封印：革命 → 120级班·雷昂（任务600006）
    {theme: "王室封印：用主线纪念物、月石和五彩水晶完成认证",
       bosses: [5220003],
     materials: [
         [4000313, 50],    // 黄金枫叶
         [4011007, 20],    // 月石
         [4251200, 2],    // 下等五彩水晶
         [4260009, 10]     // 强化宝石
         [4000225, 1]     // 强化宝石
         [4000231, 100]     // 强化宝石
         [4000230, 100]     // 强化宝石
         [4000232, 100]     // 强化宝石
         [4000233, 100]     // 强化宝石
         [4000234, 100]     // 强化宝石
         [4000236, 100]     // 强化宝石
         [4000237, 100]     // 强化宝石
         [4000238, 100]     // 强化宝石
         [4000239, 100]     // 强化宝石
         [4000240, 100]     // 强化宝石
         [4000241, 100]     // 强化宝石
         [4000242, 100]     // 强化宝石
     ],
     meso: 100000000, cash: 10000, chance: 65, pity: 8},

    // 级8  狮王共鸣：120级班·雷昂 → 125级班·雷昂
    {theme: "狮王共鸣：用四种下等属性宝石与日月精华唤醒套装",
     bosses: [6220000, 6220001],
     materials: [
         [4250800, 50],    // 下等力量水晶
         [4250900, 50],    // 下等智慧水晶
         [4251000, 50],    // 下等幸运水晶
         [4251100, 50],    // 下等敏捷水晶
         [4011007, 20],    // 月石
         [4021009, 20]     // 星石
         [4000254, 100]     // 星石
         [4000255, 100]     // 星石
         [4000256, 100]     // 星石
         [4000257, 100]     // 星石
         [4000258, 100]     // 星石
         [4000259, 100]     // 星石
         [4000260, 100]     // 星石
         [4000264, 100]     // 星石
         [4000265, 100]     // 星石
         [4000282, 100]     // 星石
     ],
     meso: 100000000, cash: 10000, chance: 55, pity: 8},

    // 级9  皇家试炼：125级班·雷昂 → 皇家班·雷昂（任务31180）
    {theme: "皇家试炼：青竹武士与九尾狐资格加三种中等宝石",
      bosses: [6090002, 7220001],
     materials: [
         [4250001, 100],    // 苔藓木妖
         [4251301, 50],    // 中等黑水晶
         [4251401, 50],    // 中等黑暗水晶
         [4260009, 50]     // 强化宝石
         [4000353, 100]     // 强化宝石
         [4000354, 100]     // 强化宝石
         [4000355, 100]     // 强化宝石
         [4000356, 100]     // 强化宝石
         [4000357, 100]     // 强化宝石
         [4000443, 100]     // 强化宝石
         [4000444, 100]     // 强化宝石
         [4000448, 100]     // 强化宝石
         [4000500, 100]     // 强化宝石
         [4000503, 100]     // 强化宝石
         [4000530, 100]     // 强化宝石
         [4000532, 100]     // 强化宝石
         [4000534, 100]     // 强化宝石
     ],
     meso: 100000000, cash: 10000, chance: 50, pity: 8},

    // 级10 异星校准：皇家班·雷昂 → 外星人混合套（任务600007）
    {theme: "异星校准：以钻机或狮王掉落的红色钻石融合两套装备",
     quests: [600007],
     materials: [
         [4032133, 3],    // 红色钻石
         [4011007, 10],    // 月石
         [4021009, 10],    // 星石
         [4251300, 10]     // 下等黑水晶

     ],
     meso: 100000000, cash: 10000, chance: 45, pity: 8},

    // 级11 武陵猎证：外星人混合套 → 法弗纳+芬撒里尔/女皇防具（route: pensalir）
    {theme: "武陵猎证：收集肯德熊熊掌与妖怪禅师娃娃",
     route: "pensalir", bosses: [7220000, 7220002],
     materials: [
         [4000283, 10],   // 熊掌
         [4000289, 10],   // 猫咪娃娃
         [4251200, 1],    // 下等五彩水晶
         [4000313, 5]     // 黄金枫叶
     ],
     meso: 100000000, cash: 10000, chance: 40, pity: 8},

    // 级12 女皇祝福：外星人混合套 → 法弗纳+女皇防具（route: empress）
    {theme: "女皇祝福：以艾利杰角尾、星石和希纳斯宝石授勋",
     route: "empress", bosses: [8220000, 8850011],
     materials: [
         [4000073, 20],   // 独角狮硬角
         [4000074, 20],   // 黑色飞狮尾
         [4021009, 20],    // 星石
         [4260009, 20]     // 强化宝石
     ],
     meso: 100000000, cash: 10000, chance: 35, pity: 9},

    // 级13 时空三印：法弗纳防具套 → 埃苏莱布斯+战国防具
    {theme: "时空三印：吉米拉、小吃店与阿卡伊勒共同开启高阶锻造",
     bosses: [8220002, 8220009, 8860000],
     materials: [
         [4260009, 30],    // 强化宝石
         [4250001, 20],    // 苔藓木妖
         [4251301, 20],    // 中等黑水晶
         [4011007, 20],    // 月石
         [4021009, 20]     // 星石
     ],
     meso: 100000000, cash: 10000, chance: 30, pity: 9},

    // 级14 深渊合铸：埃苏莱布斯+战国防具 → 漩涡+埃苏莱布斯防具
    {theme: "深渊合铸：大海兽与鲁塔比斯四守卫资格激活五晶核心",
     bosses: [8220003, 8910100, 8900100, 8920101, 8930100],
     materials: [
         [4250801, 10],    // 中等力量水晶
         [4250901, 10],    // 中等智慧水晶
         [4251001, 10],    // 中等幸运水晶
         [4251101, 10],    // 中等敏捷水晶
         [4251302, 10],    // 高等黑水晶
         [4260009, 50]     // 强化宝石
     ],
     meso: 60000000, cash: 15000, chance: 25, pity: 10},

    // 级15 奥术成长：漩涡防具套 → 神秘之影整套（任务34102~34105）
    {theme: "奥术成长：完成奥术河任务并以核心宝石和高阶宝石突破",
     quests: [34102, 34103, 34104, 34105],
     materials: [
         [2435719, 150],   // 核心宝石
         [4250002, 10],    // 高等钻石
         [4251302, 10],    // 高等黑水晶
         [4251401, 1]     // 中等黑暗水晶
     ],
     meso: 80000000, cash: 20000, chance: 20, pity: 10},

    // 级16 神说终章：神秘之影 → 天命/永恒整套
    {theme: "神说终章：七位神说Boss的强化宝石与少量时间之石共鸣",
     bosses: [8870000, 8870200, 8880400, 8880200, 8645009, 8880700, 8880803],
     materials: [
         [2435719, 300],   // 核心宝石
         [4021010, 30],    // 时间之石
         [4011007, 30],    // 月石
         [4021009, 30],    // 星石
         [4260009, 70]     // 强化宝石
     ],
     meso: 120000000, cash: 30000, chance: 20, pity: 10}
];

// Boss id → 显示名（用于资格检查提示）
var BOSS_NAMES = {
    2220000: "红蜗牛王", 9400610: "黑暗独角兽", 9400609: "印第安老斑鸠",
    9400613: "沃勒福", 9400612: "牛魔王", 9400611: "雪之猫女", 9400633: "牛魔王",
    3220000: "树妖王", 3220001: "大宇", 4220001: "歇尔夫", 5220002: "浮士德",
    5220004: "巨型蜈蚣", 5220001: "巨居蟹", 5220003: "提莫", 6220000: "多尔",
    6220001: "朱诺", 6090002: "青竹武士", 7220001: "九尾狐", 7220000: "肯德熊",
    7220002: "妖怪禅师", 8220000: "艾利杰", 8220002: "吉米拉", 8220009: "小吃店",
    8220003: "大海兽",
    8860000: "阿卡伊勒", 8850011: "希纳斯",
    8910100: "半半", 8900100: "皮埃尔", 8920101: "血腥女王", 8930100: "贝伦",
    8870000: "希拉", 8870200: "白发希拉", 8880400: "觉醒希拉", 8880200: "卡翁",
    8645009: "敦凯尔", 8880700: "守护天使绿水灵", 8880803: "监视者卡洛斯"
};

// Boss id → 所在地图 id（仅作提示，本菜单不传送）
var BOSS_MAPS = {
    2220000: 104000400, 9400610: 677000003, 9400609: 677000005, 9400613: 677000009,
    9400612: 677000001, 9400611: 677000007, 9400633: 677000012, 3220000: 101030404,
    3220001: 260010201, 4220001: 230020100, 5220002: 100040105, 5220004: 251010102,
    5220001: 110040000, 5220003: 220050000, 6220000: 107000300, 6220001: 221040301,
    6090002: 800020120, 7220001: 222010310, 7220000: 250010304, 7220002: 250010504,
    8220000: 200010300, 8220002: 261030000, 8220009: 105090310, 8220003: 240040401
};

// ----------------------------------------------------------------------------
// 运行时状态
// ----------------------------------------------------------------------------
var status = -1;
var selectedMode = null;       // "starter" / "evolve" / "preview"
var selectedRecipe = null;
var selectedSourceIds = null;
var availableRecipes = [];
var setRecipes = buildSetRecipes();   // 预生成所有职业 × 所有路线的进化配方

// NPC 入口
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

// 主菜单：展示初始套 + 检测到的可进化路线
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

    // 初始套（仅首次可兑换）
    if (cm.getCharacterExtendValue(STARTER_KEY) !== "1") {
        var starterItems = getSetItems(SHARED_SETS[0], jobIndex);
        text += "#L0##b兑换45级冒险岛宝石整套#k\r\n";
        text += formatSetPreview(starterItems) + "\r\n";
        text += "玩法：" + STARTER_RULE.theme + "\r\n";
        text += buildOwnedCostText(STARTER_RULE) + "#l\r\n";
    }

    // 检测装备栏中可进化的完整六件套
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
            text += "玩法：" + availableRecipes[i].rule.theme + "\r\n";
            if (match) {
                availableRecipes[i].menuSourceIds = itemIds(match);
            }
        }
    }

    cm.sendSimple(text);
}

// 处理主菜单选择
function handleMainSelection(selection) {
    // 选项 0：兑换初始套
    if (selection === 0) {
        selectedMode = "starter";
        var starterItems = getSetItems(SHARED_SETS[0], getJobIndex());
        cm.sendYesNo(TITLE
            + "#e兑换整套装备：#n\r\n" + formatDetailedPreview(starterItems)
            + "\r\n#e阶段玩法：#n" + STARTER_RULE.theme + "\r\n"
            + "\r\n#e需要收集：#n\r\n" + buildCostText(STARTER_RULE)
            + buildQualificationText(STARTER_RULE)
            + "\r\n确定兑换吗？");
        return;
    }

    // 选项 100+i：进化对应路线
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

// 预览子菜单
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

// 预览内容
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
        text += "#d" + VISITOR_ALIEN_SLOT_NOTE + "#k\r\n";
        text += "\r\n#b" + VISITOR_ALIEN_SET.name + "混合套#k "
            + formatSetPreview(getVisitorAlienSetItems(jobIndex, 0).slice(1));
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
        var visitorWeapon = VISITOR_ALIEN_SET.weapons[jobIndex][selection - 910];
        text += "\r\n#b" + VISITOR_ALIEN_SET.name + "#k  #v" + visitorWeapon
            + "# #z" + visitorWeapon + "#";
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

// 兑换初始套
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

// 执行整套进化
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

    // 成功：移除来源六件套，发放目标整套
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

// 按配方生成目标装备（并继承来源装备的强化等属性）
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

// 把来源装备的强化增量、星级、标记等继承到目标装备
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

// 组装确认对话
function buildConfirmation(recipe, sourceIds) {
    var failures = getFailureCount(recipe);
    var costs = getSetCosts(recipe);
    var text = TITLE
        + "#e来源整套：" + recipe.sourceName + "#n\r\n" + formatDetailedPreview(sourceIds)
        + "\r\n#e目标整套：" + recipe.targetName + "#n\r\n" + formatDetailedPreview(recipe.targetIds);
    if (recipe.sourceName.indexOf(VISITOR_ALIEN_SET.name) >= 0
            || recipe.targetName.indexOf(VISITOR_ALIEN_SET.name) >= 0) {
        text += "\r\n#d" + VISITOR_ALIEN_SLOT_NOTE + "#k";
    }
    text += "\r\n#e阶段玩法：#n" + recipe.rule.theme + "\r\n"
        + "\r\n#e整套消耗：#n\r\n" + buildCostText(costs)
        + "当前成功率：#r" + getCurrentChance(recipe, failures) + "%#k";
    if (recipe.rule.pity > 0) {
        text += "（已失败 " + failures + "/" + recipe.rule.pity + " 次）";
    }
    text += "\r\n" + buildQualificationText(recipe.rule);
    return text;
}

// 组装永久资格提示（任务/Boss 是否完成）
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

// 计算缺哪些条件（任务/Boss/材料/金币/点券）
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

// 扣除费用（材料/金币/点券）
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

// 复制一个 rule 的 cost（用于初始套，不加倍率）
function copyCosts(rule) {
    var materials = [];
    for (var i = 0; i < rule.materials.length; i++) {
        materials.push([rule.materials[i][0], rule.materials[i][1]]);
    }
    return {materials: materials, meso: rule.meso, cash: rule.cash};
}

// ★ 计算整套进化的实际 cost（这里套用倍率）★
function getSetCosts(recipe) {
    var materials = [];
    for (var i = 0; i < recipe.rule.materials.length; i++) {
        materials.push([
            recipe.rule.materials[i][0],
            Math.ceil(recipe.rule.materials[i][1] * SET_MATERIAL_SCALE)   // 材料倍率（默认1）
        ]);
    }
    return {
        materials: materials,
        meso: Math.ceil(recipe.rule.meso * SET_MESO_SCALE),               // 金币 ×6.5
        cash: Math.ceil(recipe.rule.cash * SET_CASH_SCALE)                // 点券 ×6
    };
}

// 展示 cost 文本（#i 图标 #t 名称）
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

// 初始套菜单用的"已有数量"展示
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

// 失败次数读写
function getFailureCount(recipe) {
    return parseInt(cm.getCharacterExtendValue(getFailureKey(recipe)) || "0", 10) || 0;
}

function setFailureCount(recipe, value) {
    cm.saveOrUpdateCharacterExtendValue(getFailureKey(recipe), String(value));
}

function getFailureKey(recipe) {
    return FAIL_KEY_PREFIX + recipe.sourceOptions[0][0] + "_" + recipe.route;
}

// 计算当前成功率（失败 +5%/次，封顶 +25%；达到 pity 必成功）
function getCurrentChance(recipe, failures) {
    if (recipe.rule.pity > 0 && failures >= recipe.rule.pity) {
        return 100;
    }
    return Math.min(100, recipe.rule.chance + Math.min(25, failures * 5));
}

// Boss 击杀资格
function hasBossClear(mobId) {
    return cm.getCharacterExtendValue(BOSS_KEY_PREFIX + mobId) === "1";
}

function getBossLabel(mobId) {
    var label = BOSS_NAMES[mobId] || ("Boss " + mobId);
    return BOSS_MAPS[mobId] ? label + "（#m" + BOSS_MAPS[mobId] + "#）" : label;
}

// 取当前职业在 JOB_NAMES 中的索引（0~4），不在五大系列返回 -1
function getAvailableRecipes(jobIndex) {
    var result = [];
    for (var i = 0; i < setRecipes.length; i++) {
        if (setRecipes[i].jobIndex === jobIndex && findSourceSet(setRecipes[i], null)) {
            result.push(setRecipes[i]);
        }
    }
    return result;
}

// 在装备栏中查找来源六件套（任一可选项即可）
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

// 取当前职业索引
function getJobIndex() {
    var style = Job.getJobStyleInternal(cm.getPlayer().getJob().getId(), 0);
    var niche = style.getJobNiche();
    return niche >= 1 && niche <= 5 ? niche - 1 : -1;
}

// ----------------------------------------------------------------------------
// 预生成所有「来源整套 → 目标整套」配方
// 共享套顺序进化使用 STEP_RULES[0..6]，革命→lion120 用 STEP_RULES[7]；
// 之后 lion120→lion125→royal 分别用 STEP_RULES[8]、[9]；
// 武器路线每条 7 段共用 STEP_RULES[10..16]（按 route 区分 pensalir/empress/main/arcane/destiny）。
// ----------------------------------------------------------------------------
function buildSetRecipes() {
    var result = [];
    for (var job = 0; job < 5; job++) {
        // 共享套顺序进化（宝石→铂金→…→革命）
        for (var shared = 0; shared < SHARED_SETS.length - 1; shared++) {
            addFullSetRecipe(
                result,
                getSetItems(SHARED_SETS[shared], job), null,
                getSetItems(SHARED_SETS[shared + 1], job),
                job, STEP_RULES[shared], SHARED_SETS[shared].name,
                SHARED_SETS[shared + 1].name, "early_" + shared, null, null
            );
        }

        // 革命 → 120级班·雷昂 → 125级班·雷昂 → 皇家班·雷昂
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

        // 武器路线：每条武器 7 段共用 STEP_RULES[10..16]
        var paths = WEAPON_PATHS[job];
        for (var pathIndex = 0; pathIndex < paths.length; pathIndex++) {
            var path = paths[pathIndex];
            var route = "weapon_" + path.items[0];
            var royal = BRANCH_SETS.royal.items[job];
            var visitorAlien = getVisitorAlienSetItems(job, pathIndex);
            var fafnirPensalir = combineWeaponAndArmor(path.items[0], BRANCH_SETS.pensalir.items[job]);
            var fafnirEmpress = combineWeaponAndArmor(path.items[0], BRANCH_SETS.empress.items[job]);
            var absolabSengoku = combineWeaponAndArmor(path.items[1], BRANCH_SETS.sengoku.items[job]);
            var sweetwaterAbsolab = combineWeaponAndArmor(path.items[2], BRANCH_SETS.absolab.items[job]);
            var arcaneSet = combineWeaponAndArmor(path.items[3], BRANCH_SETS.arcane.items[job]);
            var destinySet = getFinalSetItems(job, path);

            addFullSetRecipe(
                result, royal, "royal", visitorAlien,
                job, STEP_RULES[10], BRANCH_SETS.royal.name,
                VISITOR_ALIEN_SET.name + path.name + "混合套",
                route + "_visitor_alien", null, null
            );
            addFullSetRecipe(
                result, visitorAlien, null, fafnirPensalir,
                job, STEP_RULES[11], VISITOR_ALIEN_SET.name + path.name + "混合套",
                "法弗纳" + path.name + " + " + BRANCH_SETS.pensalir.name + "防具",
                route + "_pensalir", WEAPON_LEVEL_EXPAND[0], WEAPON_MAX_STAR[0]
            );
            addFullSetRecipe(
                result, visitorAlien, null, fafnirEmpress,
                job, STEP_RULES[12], VISITOR_ALIEN_SET.name + path.name + "混合套",
                "法弗纳" + path.name + " + " + BRANCH_SETS.empress.name + "防具",
                route + "_empress", WEAPON_LEVEL_EXPAND[0], WEAPON_MAX_STAR[0]
            );
            addFullSetRecipe(
                result, fafnirPensalir, null, absolabSengoku,
                job, STEP_RULES[13], "法弗纳" + path.name + " + " + BRANCH_SETS.pensalir.name + "防具",
                "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                route + "_pensalir", WEAPON_LEVEL_EXPAND[1], WEAPON_MAX_STAR[1]
            );
            addFullSetRecipe(
                result, fafnirEmpress, null, absolabSengoku,
                job, STEP_RULES[13], "法弗纳" + path.name + " + " + BRANCH_SETS.empress.name + "防具",
                "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                route + "_empress", WEAPON_LEVEL_EXPAND[1], WEAPON_MAX_STAR[1]
            );
            addFullSetRecipe(
                result, absolabSengoku, "sengoku", sweetwaterAbsolab,
                job, STEP_RULES[14], "埃苏莱布斯" + path.name + " + " + BRANCH_SETS.sengoku.name + "防具",
                "漩涡" + path.name + " + " + BRANCH_SETS.absolab.name + "防具",
                route + "_main", WEAPON_LEVEL_EXPAND[2], WEAPON_MAX_STAR[2]
            );
            addFullSetRecipe(
                result, sweetwaterAbsolab, null, arcaneSet,
                job, STEP_RULES[15], "漩涡" + path.name + " + " + BRANCH_SETS.absolab.name + "防具",
                "神秘之影" + path.name + "整套",
                route + "_arcane", WEAPON_LEVEL_EXPAND[3], WEAPON_MAX_STAR[3]
            );
            addFullSetRecipe(
                result, arcaneSet, null, destinySet,
                job, STEP_RULES[16], "神秘之影" + path.name + "整套",
                BRANCH_SETS.destiny.name + path.name + "整套",
                route + "_destiny", WEAPON_LEVEL_EXPAND[4], WEAPON_MAX_STAR[4]
            );
        }
    }
    return result;
}

// 注册一条完整六件套进化配方
function addFullSetRecipe(result, sourceItems, sourceStage, targetItems, jobIndex, rule,
                          sourceName, targetName, route, levelExpand, maxStar) {
    result.push({
        sourceOptions: getSourceOptions(sourceItems, sourceStage, jobIndex),
        targetIds: targetItems.slice(0),
        // 继承映射：目标第 i 件继承自来源第 i 件；天命拆分 7 件时第3件(裤子)不继承(-1)
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

// 来源可选装备：基础为每件固定 id；特定阶段允许同部位替代件（帽子/鞋/披风）
function getSourceOptions(items, stage, jobIndex) {
    var options = [];
    for (var i = 0; i < items.length; i++) {
        options.push([items[i]]);
    }

    if (stage === "lion120") {
        options[4].push(1072239, 1072344);                 // 鞋替代件
    } else if (stage === "lion125") {
        options[4].push(1072732);                          // 鞋替代件
        options[5].push(1102471 + jobIndex);               // 披风替代件
    } else if (stage === "royal") {
        options[1].push(1004637);                          // 帽替代件
        options[4].push(1072737);                          // 鞋替代件
        options[5].push(1102476 + jobIndex);               // 披风替代件
    } else if (stage === "sengoku") {
        options[1].push(1003621);                          // 帽替代件
        options[4].push(1072743);                          // 鞋替代件
        options[5].push(1102481 + jobIndex);               // 披风替代件
    }
    return options;
}

// 组合武器 + 防具（武器在前，防具取第2件起）
function combineWeaponAndArmor(weaponId, setItems) {
    return [weaponId].concat(setItems.slice(1));
}

// 外星人混合套：武器(按路线) + 五个防具部位
function getVisitorAlienSetItems(jobIndex, pathIndex) {
    return [VISITOR_ALIEN_SET.weapons[jobIndex][pathIndex]].concat(VISITOR_ALIEN_SET.armor);
}

// 最终套：武器 + 天命防具（上衣/裤/手套/鞋/披风），裤子单独拆出为第4件
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

// 从套装定义取六件套 [武器, 帽, 上衣, 手套, 鞋, 披风]
function getSetItems(set, jobIndex) {
    return [set.weapons[jobIndex], set.armor[0], set.armor[1], set.armor[2], set.armor[3], set.armor[4]];
}

// 套装图标预览（横向 #v）
function formatSetPreview(items) {
    var text = "";
    for (var i = 0; i < items.length; i++) {
        text += "#v" + items[i] + "#";
    }
    return text;
}

// 套装详细预览（图标 + 名称，两个一行）
function formatDetailedPreview(items) {
    var text = "";
    for (var i = 0; i < items.length; i++) {
        text += "#v" + items[i] + "# #z" + items[i] + "#";
        text += i % 2 === 1 || i === items.length - 1 ? "\r\n" : "    ";
    }
    return text;
}

// 数值限幅（short 范围）
function clampShort(value) {
    return Math.max(-32768, Math.min(32767, value));
}

// 千分位格式化
function formatNumber(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
