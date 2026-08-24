// ============================================================================
// 装备升级系统（全新）
// 20阶段单件升级 · 100%成功 · 双路线(套服/上下服) · 16条武器链
// 条件：矿石·宝石·怪物掉落·击杀数量·任务·BOSS·装备献祭·金币·点券
// ============================================================================

var InventoryType = Java.type("org.gms.client.inventory.InventoryType");
var InventoryManipulator = Java.type("org.gms.client.inventory.manipulator.InventoryManipulator");
var ItemInformationProvider = Java.type("org.gms.server.ItemInformationProvider");
var Job = Java.type("org.gms.client.Job");

// ---- 职业 ----
var JOB_NAMES = ["战士", "法师", "弓箭手", "飞侠", "海盗"];

// ---- 存档键 ----
var STAGE_KEY_PREFIX = "equip_upgrade_stage_";
var BRANCH_KEY = "equip_upgrade_armor_branch";
var KILL_KEY_PREFIX = "equip_upgrade_kill_";
var BOSS_KEY_PREFIX = "equip_upgrade_boss_";

// ---- BOSS名称 ----
var BOSS_NAMES = {
    2220000:"红蜗牛王",3220000:"树妖王",3220001:"大宇",4220001:"歇尔夫",
    5220002:"浮士德",5220004:"巨型蜈蚣",5220001:"巨居蟹",5220003:"提莫",
    6220000:"多尔",6220001:"朱诺",6090002:"青竹武士",7220001:"九尾狐",
    7220000:"肯德熊",7220002:"妖怪禅师",8220000:"艾利杰",8850011:"希纳斯",
    8220002:"吉米拉",8220009:"小吃店",8860000:"阿卡伊勒",8220003:"大海兽",
    8910100:"半半",8900100:"皮埃尔",8920101:"血腥女王",8930100:"贝伦",
    8870000:"希拉",8870200:"白发希拉",8880400:"觉醒希拉",8880200:"卡翁",
    8645009:"敦凯尔",8880700:"守护天使绿水灵",8880803:"监视者卡洛斯"
};

// ============================================================================
// 防具升级配置（20阶段）
// shared: 全职业通用部位 | branches: longcoat/coatPants 两条路线
// ============================================================================
var ARMOR_STAGES = [
    {name:"木制套装",level:10,
     shared:{cap:1002002,glove:1082005,shoes:1072005,cape:1102039},
     branches:{longcoat:{longcoat:1050006},coatPants:{coat:1040009,pants:1060009}},
     conditions:{items:[[4000000,200],[4000016,200],[4000019,200],[4000009,150],[4000012,150],[4000005,150],[4000002,150],[4000006,120],[4000037,120],[4000042,120],[4010000,120],[4000195,120]],
        quests:[1007,1008],bosses:[],killCount:{minLevel:10,count:200},meso:100000,cash:0,equipSacrifice:[]}},
    {name:"铁制套装",level:20,
     shared:{cap:1002005,glove:1082010,shoes:1072010,cape:1102040},
     branches:{longcoat:{longcoat:1050022},coatPants:{coat:1040012,pants:1060012}},
     conditions:{items:[[4000008,200],[4000015,200],[4000017,200],[4000013,200],[4000010,150],[4000018,150],[4000025,150],[4000034,150],[4000097,120],[4000324,120],[4000042,120],[4011001,120],[4020000,120],[4003000,120]],
        quests:[2049,2145],bosses:[],killCount:{minLevel:20,count:300},meso:300000,cash:0,equipSacrifice:[]}},
    {name:"紫矿套装",level:30,
     shared:{cap:1002011,glove:1082015,shoes:1072015,cape:1102041},
     branches:{longcoat:{longcoat:1050029},coatPants:{coat:1040020,pants:1060020}},
     conditions:{items:[[4000020,300],[4000021,300],[4000024,250],[4000032,250],[4000026,200],[4000029,200],[4000031,150],[4000035,150],[4000059,150],[4000043,120],[4000300,120],[4020001,120],[4003000,120],[4003001,120],[4000034,120],[4000097,120]],
        quests:[2178,2185,2247],bosses:[],killCount:{minLevel:30,count:400},meso:1000000,cash:0,equipSacrifice:[]}},
    {name:"黄金套装",level:40,
     shared:{cap:1002020,glove:1082020,shoes:1072020,cape:1102042},
     branches:{longcoat:{longcoat:1050038},coatPants:{coat:1040033,pants:1060033}},
     conditions:{items:[[4000014,250],[4000036,250],[4000044,200],[4000045,200],[4000048,200],[4000058,200],[4000060,180],[4000076,150],[4000078,150],[4000276,150],[4000031,150],[4011006,120],[4021000,120],[4020002,120],[4020004,120],[4003000,120],[4003001,120]],
        quests:[2248,2249,2256],bosses:[],killCount:{minLevel:40,count:500},meso:3000000,cash:3000,equipSacrifice:[]}},
    {name:"冒险岛宝石套装",level:50,
     shared:{cap:1003242,glove:1082314,shoes:1072521,cape:1102294},
     branches:{longcoat:{longcoat:1052357},coatPants:{coat:1052357,pants:1062000}},
     conditions:{items:[[4000022,300],[4000025,250],[4000027,250],[4000028,200],[4000053,200],[4000067,180],[4000073,150],[4000172,150],[4000300,150],[4011007,120],[4021001,120],[4021003,120],[4005000,120],[4005001,120],[4000313,120],[4000324,120],[4000034,120]],
        quests:[2148,2149,2150,2151],bosses:[2220000],killCount:{minLevel:50,count:600},meso:8000000,cash:5000,equipSacrifice:[{level:30,count:1,slot:"weapon"}]}},
    {name:"冒险岛铂金套装",level:60,
     shared:{cap:1003243,glove:1082315,shoes:1072522,cape:1102295},
     branches:{longcoat:{longcoat:1052358},coatPants:{coat:1052358,pants:1062001}},
     conditions:{items:[[4000073,300],[4000074,250],[4000079,250],[4000080,200],[4000226,200],[4000229,200],[4000046,180],[4000054,150],[4000413,150],[4000053,150],[4000028,150],[4021007,120],[4021006,120],[4005002,120],[4005003,120],[4001126,120],[4000313,120],[4000226,120],[4000059,120]],
        quests:[2152,2209,2214,2215],bosses:[3220000,3220001],killCount:{minLevel:60,count:800},meso:15000000,cash:8000,equipSacrifice:[]}},
    {name:"斯泰拉套装",level:70,
     shared:{cap:1003723,glove:1082494,shoes:1072761,cape:1102502},
     branches:{longcoat:{longcoat:1052553},coatPants:{coat:1052553,pants:1062002}},
     conditions:{items:[[4000130,300],[4000131,250],[4000132,250],[4000145,200],[4000146,200],[4000147,200],[4000080,180],[4000179,150],[4000180,150],[4000134,150],[4000073,150],[4021008,120],[4250000,120],[4250001,120],[4003000,120],[4032474,120],[4000226,120],[4000059,120]],
        quests:[3043,3045,3046,3047],bosses:[4220001],killCount:{minLevel:70,count:1000},meso:20000000,cash:10000,equipSacrifice:[{level:50,count:1,slot:"any"}]}},
    {name:"传说冒险岛套装",level:80,
     shared:{cap:1003364,glove:1082391,shoes:1072610,cape:1102322},
     branches:{longcoat:{longcoat:1052405},coatPants:{coat:1052405,pants:1062003}},
     conditions:{items:[[4000133,300],[4000135,250],[4000148,250],[4000149,200],[4000150,200],[4000182,200],[4000183,200],[4000184,180],[4000283,150],[4000289,150],[4000130,150],[4021009,120],[4250800,120],[4250900,120],[4251000,120],[4251100,120],[4032133,120],[4000313,120],[4000073,120]],
        quests:[3048,3049,3050,3052,3069],bosses:[5220002,5220004],killCount:{minLevel:80,count:1200},meso:30000000,cash:12000,equipSacrifice:[]}},
    {name:"专属紫金枫叶套装",level:90,
     shared:{cap:1003552,glove:1082433,shoes:1072666,cape:1102441},
     branches:{longcoat:{longcoat:1052461},coatPants:{coat:1052461,pants:1062004}},
     conditions:{items:[[4000138,300],[4000139,250],[4000140,250],[4000151,250],[4000152,200],[4000175,200],[4000243,180],[4000266,150],[4000267,150],[4000268,150],[4000130,150],[4251200,120],[4005000,120],[4005001,120],[4005002,120],[4005003,120],[4001136,120],[4032133,120],[4000073,120]],
        quests:[3071,3076,3077,3079,3081],bosses:[5220001,5220003],killCount:{minLevel:90,count:1500},meso:50000000,cash:15000,equipSacrifice:[{level:60,count:1,slot:"weapon"}]}},
    {name:"风暴套装",level:100,
     shared:{cap:1003561,glove:1082438,shoes:1072672,cape:1102467},
     branches:{longcoat:{longcoat:1052467},coatPants:{coat:1052467,pants:1062005}},
     conditions:{items:[[4000235,300],[4000244,250],[4000245,250],[4000269,200],[4000270,200],[4000271,200],[4000272,180],[4000273,180],[4000274,150],[4000181,150],[4000448,150],[4000458,150],[4251300,120],[4251401,120],[4005004,120],[4032170,120],[4032171,120],[4032133,120],[4000073,120]],
        quests:[3082,3085,3092,3093,3094],bosses:[6220000,6220001],killCount:{minLevel:100,count:1800},meso:80000000,cash:20000,equipSacrifice:[]}},
    {name:"终极套装",level:110,
     shared:{cap:1003740,glove:1082498,shoes:1072768,cape:1102506},
     branches:{longcoat:{longcoat:1052569},coatPants:{coat:1052569,pants:1062006}},
     conditions:{items:[[4000151,300],[4000152,300],[4000461,250],[4000462,250],[4000456,200],[4000457,200],[4000459,180],[4000460,180],[4000463,150],[4000235,150],[4260009,120],[4251301,120],[4250801,120],[4250901,120],[4001136,120],[4032133,120],[4000313,120],[4000073,120],[4000074,120]],
        quests:[3103,3104,3105,3209],bosses:[6090002,7220001],killCount:{minLevel:110,count:2000},meso:100000000,cash:25000,equipSacrifice:[{level:80,count:2,slot:"any"}]}},
    {name:"革命套装",level:120,
     shared:{cap:1003946,glove:1082540,shoes:1072853,cape:1102612},
     branches:{longcoat:{longcoat:1052647},coatPants:{coat:1052647,pants:1062007}},
     conditions:{items:[[4000448,300],[4000458,300],[4000449,250],[4000450,250],[4000451,200],[4000452,200],[4000453,200],[4000454,180],[4000455,180],[4000456,150],[4000463,150],[4260009,120],[4251200,120],[4000073,120],[4000074,120],[4001198,120],[4001246,120],[4032133,120],[4000313,120]],
        quests:[3220,5009,5010,5011,5012],bosses:[7220000,7220002],killCount:{minLevel:120,count:2500},meso:120000000,cash:30000,equipSacrifice:[{level:100,count:1,slot:"weapon"}]}},
    {name:"120级班·雷昂套装",level:130,
     shared:{cap:1003154,glove:1082285,shoes:1072471,cape:1102262},
     branches:{longcoat:{longcoat:1052299},coatPants:{coat:1052299,pants:1062008}},
     conditions:{items:[[4000448,300],[4000458,300],[4000461,250],[4000462,250],[4000435,200],[4001094,200],[4000463,180],[4000464,180],[4001755,150],[4001756,150],[4260009,120],[4250002,120],[4005004,120],[4032474,120],[4032266,120],[4032133,120],[4001136,120],[4000313,120],[4000073,120]],
        quests:[4014,4415,4416,4417,4418],bosses:[8220000,8850011],killCount:{minLevel:130,count:3000},meso:150000000,cash:35000,equipSacrifice:[{level:100,count:3,slot:"any"}]}},
    {name:"125级班·雷昂套装",level:135,
     shared:{cap:1003290,glove:1082338,shoes:1072554,cape:1102312},
     branches:{longcoat:{longcoat:1052384},coatPants:{coat:1052384,pants:1062009}},
     conditions:{items:[[4000448,300],[4000458,300],[4001094,250],[4000461,250],[4000462,250],[4001755,200],[4001756,200],[4006000,180],[4006001,180],[4001241,150],[4001242,150],[4260009,120],[4251301,120],[4251401,120],[4000353,120],[4032133,120],[4001136,120],[4000313,120],[4000073,120]],
        quests:[4402,4403,4488,4646,4647],bosses:[8220002,8220009],killCount:{minLevel:135,count:3500},meso:180000000,cash:40000,equipSacrifice:[{level:110,count:1,slot:"weapon"}]}},
    {name:"皇家班·雷昂套装",level:140,
     shared:{cap:1004234,glove:1082613,shoes:1072972,cape:1102713},
     branches:{longcoat:{longcoat:1052804},coatPants:{coat:1052804,pants:1062010}},
     conditions:{items:[[4000448,300],[4000458,300],[4001094,300],[4000435,250],[4001755,250],[4001756,250],[4006000,200],[4006001,200],[4001241,180],[4001242,180],[4260009,120],[4250801,120],[4250901,120],[4251001,120],[4251101,120],[4032133,120],[4032170,120],[4032171,120],[4000313,120]],
        quests:[4659,4660,4512,4513,4522],bosses:[8860000],killCount:{minLevel:140,count:4000},meso:200000000,cash:50000,equipSacrifice:[{level:120,count:2,slot:"any"},{level:120,count:1,slot:"weapon"}]}},
    {name:"埃苏莱布斯套装",level:150,
     shared:{cap:1004422,glove:1082636,shoes:1073030,cape:1102775},
     branches:{longcoat:{longcoat:1052882},coatPants:{coat:1052882,pants:1062011}},
     conditions:{items:[[4000448,300],[4000458,300],[4001094,300],[4001755,300],[4001756,300],[4006000,250],[4006001,250],[4007000,150],[4001241,180],[4001242,180],[4260009,120],[4251302,120],[4250002,120],[4032133,120],[4000313,120],[4000073,120],[4000074,120],[4001198,120]],
        quests:[4523,7101,7102,7104,7105],bosses:[8220003,8910100,8900100],killCount:{minLevel:150,count:4500},meso:250000000,cash:60000,equipSacrifice:[{level:130,count:2,slot:"weapon"},{level:130,count:2,slot:"any"}]}},
    {name:"漩涡套装",level:160,
     shared:{cap:1004808,glove:1082695,shoes:1073158,cape:1102940},
     branches:{longcoat:{longcoat:1053063},coatPants:{coat:1053063,pants:1062012}},
     conditions:{items:[[4000645,150],[4001755,300],[4001756,300],[4007000,200],[2435719,120],[4260009,120],[4250901,120],[4251001,120],[4251101,120],[4251302,120],[4032133,120],[4032170,120],[4032171,120],[4000313,120],[4000073,120]],
        quests:[7106,7107,7109,7301,7302],bosses:[8920101,8930100],killCount:{minLevel:160,count:5000},meso:300000000,cash:80000,equipSacrifice:[{level:140,count:2,slot:"weapon"},{level:140,count:3,slot:"any"}]}},
    {name:"神秘之影套装",level:170,
     shared:{cap:1004809,glove:1082696,shoes:1073159,cape:1102941},
     branches:{longcoat:{longcoat:1053064},coatPants:{coat:1053064,pants:1062013}},
     conditions:{items:[[4000645,200],[4001755,300],[4001756,300],[4007000,200],[2435719,200],[4021010,120],[4260009,120],[4251302,120],[4250002,120],[4250802,120],[4250902,120],[4251002,120],[4251102,120],[4032133,120],[4000313,120]],
        quests:[9004,9843,9848,9878,9902],bosses:[8870000,8870200],killCount:{minLevel:170,count:5000},meso:400000000,cash:100000,equipSacrifice:[{level:150,count:2,slot:"weapon"},{level:150,count:3,slot:"any"}]}},
    {name:"天命套装",level:185,
     shared:{cap:1005980,glove:1082760,shoes:1073629,cape:1103433},
     branches:{longcoat:{longcoat:1042433},coatPants:{coat:1042433,pants:1062285}},
     conditions:{items:[[4000645,250],[4001755,300],[4001756,300],[2435719,300],[4021010,120],[4260009,120],[4250002,120],[4250802,120],[4250902,120],[4251002,120],[4251102,120],[4251302,120],[4032133,120],[4039020,120],[4032170,120],[4032171,120]],
        quests:[9903,9904,9905,9906,9907],bosses:[8880400,8880200,8645009],killCount:{minLevel:185,count:5000},meso:500000000,cash:150000,equipSacrifice:[{level:160,count:3,slot:"weapon"},{level:160,count:4,slot:"any"}]}},
    {name:"永恒套装",level:200,
     shared:{cap:1005981,glove:1082761,shoes:1073630,cape:1103434},
     branches:{longcoat:{longcoat:1042434},coatPants:{coat:1042434,pants:1062286}},
     conditions:{items:[[4000645,300],[4001755,300],[4001756,300],[2435719,500],[4021010,150],[4260009,150],[4250002,150],[4251302,150],[4250802,120],[4250902,120],[4251002,120],[4251102,120],[4032133,120],[4001136,120],[2049115,120],[4039020,120],[4032170,120],[4032171,120],[4000313,120]],
        quests:[9908,9909,9955,200001,200002],bosses:[8880700,8880803],killCount:{minLevel:200,count:5000},meso:600000000,cash:200000,equipSacrifice:[{level:180,count:3,slot:"weapon"},{level:180,count:5,slot:"any"}]}}
];

// ============================================================================
// 武器升级配置（按职业 × 武器类型）
// WEAPON_PATHS[jobIndex] = [{name, items:[20个id]}, ...]
// ============================================================================
var WEAPON_PATHS = [
    [{name:"单手剑",items:[1302001,1302006,1302008,1302009,1302010,1302011,1302012,1302169,1302170,1302257,1302192,1302227,1302193,1302175,1302316,1302275,1302333,1302297,1302343,1302376]},
     {name:"双手剑",items:[1402000,1402006,1402008,1402009,1402010,1402011,1402012,1402169,1402170,1402257,1402192,1402227,1402193,1402175,1402316,1402275,1402333,1402297,1402343,1402376]},
     {name:"单手斧",items:[1312000,1312006,1312008,1312009,1312010,1312011,1312012,1312169,1312170,1312257,1312192,1312227,1312193,1312175,1312316,1312275,1312333,1312297,1312343,1312376]},
     {name:"双手斧",items:[1412000,1412006,1412008,1412009,1412010,1412011,1412012,1412169,1412170,1412257,1412192,1412227,1412193,1412175,1412316,1412275,1412333,1412297,1412343,1412376]},
     {name:"单手锤",items:[1322000,1322006,1322008,1322009,1322010,1322011,1322012,1322169,1322170,1322257,1322192,1322227,1322193,1322175,1322316,1322275,1322333,1322297,1322343,1322376]},
     {name:"双手锤",items:[1422000,1422006,1422008,1422009,1422010,1422011,1422012,1422169,1422170,1422257,1422192,1422227,1422193,1422175,1422316,1422275,1422333,1422297,1422343,1422376]},
     {name:"枪",items:[1432000,1432006,1432008,1432009,1432010,1432011,1432012,1432169,1432170,1432257,1432192,1432227,1432193,1432175,1432316,1432275,1432333,1432297,1432343,1432376]},
     {name:"矛",items:[1442000,1442006,1442008,1442009,1442010,1442011,1442012,1442169,1442170,1442257,1442192,1442227,1442193,1442175,1442316,1442275,1442333,1442297,1442343,1442376]}],
    [{name:"短杖",items:[1372001,1372006,1372008,1372009,1372010,1372011,1372012,1372169,1372170,1372257,1372192,1372227,1372193,1372175,1372208,1372275,1372333,1372297,1372343,1372376]},
     {name:"长杖",items:[1382000,1382006,1382008,1382009,1382010,1382011,1382012,1382169,1382170,1382257,1382192,1382227,1382193,1382175,1382204,1382275,1382333,1382297,1382343,1382376]}],
    [{name:"弓",items:[1452001,1452006,1452008,1452009,1452010,1452011,1452012,1452169,1452170,1452257,1452192,1452227,1452193,1452175,1452239,1452275,1452333,1452297,1452343,1452376]},
     {name:"弩",items:[1462000,1462006,1462008,1462009,1462010,1462011,1462012,1462169,1462170,1462257,1462192,1462227,1462193,1462175,1462225,1462275,1462333,1462297,1462343,1462376]}],
    [{name:"短刀",items:[1332001,1332006,1332008,1332009,1332010,1332011,1332012,1332169,1332170,1332257,1332192,1332227,1332193,1332175,1332261,1332275,1332333,1332297,1332343,1332376]},
     {name:"拳套",items:[1472000,1472006,1472008,1472009,1472010,1472011,1472012,1472169,1472170,1472257,1472192,1472227,1472193,1472175,1472227,1472275,1472333,1472297,1472343,1472376]}],
    [{name:"拳甲",items:[1482000,1482006,1482008,1482009,1482010,1482011,1482012,1482169,1482170,1482257,1482192,1482227,1482193,1482175,1482203,1482275,1482333,1482297,1482343,1482376]},
     {name:"短枪",items:[1492000,1492006,1492008,1492009,1492010,1492011,1492012,1492169,1492170,1492257,1492192,1492227,1492193,1492175,1492203,1492275,1492333,1492297,1492343,1492376]}]
];

// ---- 运行时 ----
var status = -1;
var mode = null;         // "armor_upgrade" / "weapon_select" / "weapon_upgrade" / "preview" / "route"
var selectedWeaponPath = -1;

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
    var weaponStage = getStage("weapon");
    var branch = cm.getCharacterExtendValue(BRANCH_KEY) || "";

    var text = "\t\t\t\t#e#r装备升级系统#k#n\r\n\r\n";
    text += "#d当前职业：#b" + JOB_NAMES[jobIdx] + "#k\r\n";

    if (armorStage >= 0) {
        text += "#d防具阶段：#b" + (armorStage + 1) + "/20 " + ARMOR_STAGES[armorStage].name + "#k\r\n";
        text += "#d衣服路线：#b" + (branch === "longcoat" ? "套服" : "上衣+裤子") + "#k\r\n";
    } else {
        text += "#d防具阶段：#r尚未开始#k\r\n";
    }

    if (weaponStage >= 0) {
        text += "#d武器阶段：#b" + (weaponStage + 1) + "/20#k\r\n";
    } else {
        text += "#d武器阶段：#r尚未开始#k\r\n";
    }

    text += "\r\n";

    // ---- 防具升级 ----
    if (armorStage + 1 < ARMOR_STAGES.length) {
        var nextStg = ARMOR_STAGES[armorStage + 1];
        text += "#L0##b防具升级 → 阶段" + (armorStage + 2) + " " + nextStg.name + " (Lv" + nextStg.level + ")#k#l\r\n";
    } else {
        text += "#d防具已达最高阶段(20/20)#k\r\n";
    }

    // ---- 武器升级（按职业显示可选武器类型）----
    var paths = WEAPON_PATHS[jobIdx];
    if (weaponStage + 1 < 20) {
        for (var i = 0; i < paths.length; i++) {
            var wStage = weaponStage >= 0 ? weaponStage : -1;
            var nextWId = paths[i].items[wStage + 1];
            var wLevel = ARMOR_STAGES[wStage + 1].level;
            text += "#L" + (10 + i) + "##b武器升级[" + paths[i].name + "] → 阶段" + (wStage + 2) + " (Lv" + wLevel + ") #v" + nextWId + "# #z" + nextWId + "##k#l\r\n";
        }
    } else {
        text += "#d武器已达最高阶段(20/20)#k\r\n";
    }

    // ---- 路线选择（首次）----
    if (armorStage < 0 && !branch) {
        text += "\r\n#e首次使用请先选择衣服路线：#n\r\n";
        text += "#L200##b选择「套服路线」（Longcoat，6件套）#k#l\r\n";
        text += "#L201##b选择「上衣+裤子路线」（Coat+Pants，7件套）#k#l\r\n";
    }

    text += "\r\n#L300##b升级路线预览#k#l\r\n";

    cm.sendSimple(text);
}

// ============================================================================
// 菜单选择
// ============================================================================
function handleMenuSelect(selection) {
    var jobIdx = getJobIndex();

    // ---- 防具升级 ----
    if (selection === 0) {
        mode = "armor_upgrade";
        var branch = cm.getCharacterExtendValue(BRANCH_KEY) || "";
        if (!branch) {
            cm.sendOk("请先在主菜单选择衣服路线（套服 或 上衣+裤子）。");
            cm.dispose(); return;
        }
        showArmorConfirm();
        return;
    }

    // ---- 武器升级（选择武器类型）----
    if (selection >= 10 && selection < 10 + 16) {
        mode = "weapon_upgrade";
        selectedWeaponPath = selection - 10;
        var paths = WEAPON_PATHS[jobIdx];
        if (selectedWeaponPath >= paths.length) {
            cm.sendOk("无效的武器选择。"); cm.dispose(); return;
        }
        showWeaponConfirm();
        return;
    }

    // ---- 路线选择 ----
    if (selection === 200) {
        cm.saveOrUpdateCharacterExtendValue(BRANCH_KEY, "longcoat");
        cm.sendOk("已选择#b套服路线#k（Longcoat，6件套）。\r\n后续所有防具升级将使用套服路线。\r\n请重新打开菜单进行升级。");
        cm.dispose(); return;
    }
    if (selection === 201) {
        cm.saveOrUpdateCharacterExtendValue(BRANCH_KEY, "coatPants");
        cm.sendOk("已选择#b上衣+裤子路线#k（7件套）。\r\n后续所有防具升级将使用上衣+裤子路线。\r\n请重新打开菜单进行升级。");
        cm.dispose(); return;
    }

    // ---- 预览 ----
    if (selection === 300) {
        showPreviewMenu();
        return;
    }

    // ---- 预览中的武器路径 ----
    if (selection >= 400 && selection < 400 + 16) {
        showWeaponPreview(selection - 400);
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
    var branch = cm.getCharacterExtendValue(BRANCH_KEY);
    var targetIds = getArmorIds(targetIdx, branch);
    var conds = stg.conditions;

    var text = "\t\t\t\t#e#r防具升级 → 阶段" + (targetIdx + 1) + " " + stg.name + "#k#n\r\n\r\n";
    text += "#e目标装备：#n\r\n" + formatPreview(targetIds) + "\r\n";
    text += "#e升级条件（100%成功）：#n\r\n";

    text += buildConditionText(conds, targetIdx);

    cm.sendYesNo(text + "\r\n\r\n#b确定升级吗？#k");
}

// ============================================================================
// 武器升级确认
// ============================================================================
function showWeaponConfirm() {
    var jobIdx = getJobIndex();
    var paths = WEAPON_PATHS[jobIdx];
    var path = paths[selectedWeaponPath];
    var curStage = getStage("weapon");
    var targetIdx = curStage + 1;
    if (targetIdx >= 20) { cm.sendOk("已达最高阶段。"); cm.dispose(); return; }

    var conds = ARMOR_STAGES[targetIdx].conditions;
    var targetId = path.items[targetIdx];
    var prevId = targetIdx > 0 ? path.items[targetIdx - 1] : 0;

    var text = "\t\t\t\t#e#r武器升级 → 阶段" + (targetIdx + 1) + "#k#n\r\n\r\n";
    text += "#e武器类型：#b" + path.name + "#k\r\n";
    text += "#e目标武器：#k#v" + targetId + "# #z" + targetId + "#\r\n";
    if (prevId > 0) text += "#e当前武器：#k#v" + prevId + "# #z" + prevId + "#\r\n";
    text += "\r\n#e升级条件（100%成功）：#n\r\n";

    // 武器本身的献祭
    if (prevId > 0) {
        text += "#r[装备献祭]#k 当前武器 #v" + prevId + "# #z" + prevId + "# × 1件\r\n";
    }

    text += buildConditionText(conds, targetIdx);

    cm.sendYesNo(text + "\r\n\r\n#b确定升级吗？#k");
}

// ============================================================================
// 条件文本构建
// ============================================================================
function buildConditionText(conds, targetIdx) {
    var text = "";

    // 装备献祭
    if (conds.equipSacrifice && conds.equipSacrifice.length > 0) {
        for (var s = 0; s < conds.equipSacrifice.length; s++) {
            var sac = conds.equipSacrifice[s];
            var slotLabel = sac.slot === "weapon" ? "武器" : sac.slot === "any" ? "任意装备" : sac.slot;
            text += "#r[装备献祭]#k Lv" + sac.level + "+ " + slotLabel + " × " + sac.count + "件\r\n";
        }
    }

    // 道具材料
    for (var i = 0; i < conds.items.length; i++) {
        var mat = conds.items[i];
        var owned = cm.getItemQuantity(mat[0]);
        text += (owned >= mat[1] ? "#g" : "#r") + "#i" + mat[0] + "# #t" + mat[0] + "# × " + mat[1]
            + "（已有 " + owned + "）#k\r\n";
    }

    // 任务
    if (conds.quests.length > 0) {
        text += "\r\n#e任务要求：#n\r\n";
        for (var q = 0; q < conds.quests.length; q++) {
            var done = cm.isQuestCompleted(conds.quests[q]);
            text += (done ? "#g[已完成]#k " : "#r[未完成]#k ") + "任务 " + conds.quests[q] + "\r\n";
        }
    }

    // BOSS
    if (conds.bosses.length > 0) {
        text += "\r\n#eBOSS击杀资格：#n\r\n";
        for (var b = 0; b < conds.bosses.length; b++) {
            var bDone = hasBossClear(conds.bosses[b]);
            var bLabel = BOSS_NAMES[conds.bosses[b]] || ("Boss " + conds.bosses[b]);
            text += (bDone ? "#g[已击杀]#k " : "#r[未击杀]#k ") + bLabel + "\r\n";
        }
    }

    // 击杀进度
    var killKey = KILL_KEY_PREFIX + targetIdx;
    var killDone = parseInt(cm.getCharacterExtendValue(killKey) || "0");
    text += "\r\n#e击杀进度：#k Lv" + conds.killCount.minLevel + "+怪物 "
        + killDone + "/" + conds.killCount.count
        + (killDone >= conds.killCount.count ? " #g[达标]#k" : " #r[未达标]#k") + "\r\n";

    // 金币/点券
    text += "\r\n金币：" + formatNum(conds.meso) + "（已有 " + formatNum(cm.getMeso()) + "）\r\n";
    if (conds.cash > 0) {
        text += "点券：" + formatNum(conds.cash) + "（已有 " + formatNum(cm.getPlayer().getCashShop().getCash(1)) + "）\r\n";
    }

    return text;
}

// ============================================================================
// 确认执行
// ============================================================================
function handleConfirm(sel) {
    if (sel !== 1) { cm.dispose(); return; }
    if (mode === "armor_upgrade") doArmorUpgrade();
    else if (mode === "weapon_upgrade") doWeaponUpgrade();
    else cm.dispose();
}

function doArmorUpgrade() {
    var curStage = getStage("armor");
    var targetIdx = curStage + 1;
    var stg = ARMOR_STAGES[targetIdx];
    var branch = cm.getCharacterExtendValue(BRANCH_KEY);
    var conds = stg.conditions;
    var targetIds = getArmorIds(targetIdx, branch);

    // 等级
    if (cm.getPlayer().getLevel() < stg.level) {
        cm.sendOk("等级不足，需要 Lv" + stg.level); cm.dispose(); return;
    }
    // 任务
    for (var q = 0; q < conds.quests.length; q++) {
        if (!cm.isQuestCompleted(conds.quests[q])) {
            cm.sendOk("任务 " + conds.quests[q] + " 未完成"); cm.dispose(); return;
        }
    }
    // BOSS
    for (var b = 0; b < conds.bosses.length; b++) {
        if (!hasBossClear(conds.bosses[b])) {
            cm.sendOk((BOSS_NAMES[conds.bosses[b]] || "Boss") + " 击杀资格未完成"); cm.dispose(); return;
        }
    }
    // 击杀
    var killDone = parseInt(cm.getCharacterExtendValue(KILL_KEY_PREFIX + targetIdx) || "0");
    if (killDone < conds.killCount.count) {
        cm.sendOk("击杀数量不足：" + killDone + "/" + conds.killCount.count); cm.dispose(); return;
    }
    // 材料
    for (var i = 0; i < conds.items.length; i++) {
        if (cm.getItemQuantity(conds.items[i][0]) < conds.items[i][1]) {
            cm.sendOk("材料不足：#t" + conds.items[i][0] + "#"); cm.dispose(); return;
        }
    }
    // 金币
    if (cm.getMeso() < conds.meso) { cm.sendOk("金币不足"); cm.dispose(); return; }
    // 点券
    if (conds.cash > 0 && cm.getPlayer().getCashShop().getCash(1) < conds.cash) {
        cm.sendOk("点券不足"); cm.dispose(); return;
    }
    // 装备栏空间
    if (cm.getPlayer().getInventory(InventoryType.EQUIP).getNumFreeSlot() < targetIds.length) {
        cm.sendOk("装备栏至少需要 " + targetIds.length + " 个空位"); cm.dispose(); return;
    }

    // 扣装备献祭
    if (!consumeSacrifice(conds.equipSacrifice)) {
        cm.sendOk("装备献祭条件不满足"); cm.dispose(); return;
    }
    // 扣上一阶段防具
    if (targetIdx > 0) consumePrevArmor(targetIdx - 1, branch);
    // 扣材料/金币/点券
    deductCosts(conds);
    // 发放新装备
    var ii = ItemInformationProvider.getInstance();
    for (var j = 0; j < targetIds.length; j++) {
        var eq = ii.getEquipById(targetIds[j]);
        if (eq) cm.gainEquip(eq);
    }
    cm.saveOrUpdateCharacterExtendValue(STAGE_KEY_PREFIX + "armor", String(targetIdx));
    cm.sendOk("防具升级成功！\r\n\r\n#b" + stg.name + "#k\r\n" + formatPreview(targetIds));
    cm.dispose();
}

function doWeaponUpgrade() {
    var jobIdx = getJobIndex();
    var path = WEAPON_PATHS[jobIdx][selectedWeaponPath];
    var curStage = getStage("weapon");
    var targetIdx = curStage + 1;
    var stg = ARMOR_STAGES[targetIdx];
    var conds = stg.conditions;
    var targetId = path.items[targetIdx];
    var prevId = targetIdx > 0 ? path.items[targetIdx - 1] : 0;

    // 等级
    if (cm.getPlayer().getLevel() < stg.level) {
        cm.sendOk("等级不足，需要 Lv" + stg.level); cm.dispose(); return;
    }
    // 任务
    for (var q = 0; q < conds.quests.length; q++) {
        if (!cm.isQuestCompleted(conds.quests[q])) {
            cm.sendOk("任务 " + conds.quests[q] + " 未完成"); cm.dispose(); return;
        }
    }
    // BOSS
    for (var b = 0; b < conds.bosses.length; b++) {
        if (!hasBossClear(conds.bosses[b])) {
            cm.sendOk((BOSS_NAMES[conds.bosses[b]] || "Boss") + " 击杀资格未完成"); cm.dispose(); return;
        }
    }
    // 击杀
    var killDone = parseInt(cm.getCharacterExtendValue(KILL_KEY_PREFIX + targetIdx) || "0");
    if (killDone < conds.killCount.count) {
        cm.sendOk("击杀数量不足"); cm.dispose(); return;
    }
    // 材料
    for (var i = 0; i < conds.items.length; i++) {
        if (cm.getItemQuantity(conds.items[i][0]) < conds.items[i][1]) {
            cm.sendOk("材料不足：#t" + conds.items[i][0] + "#"); cm.dispose(); return;
        }
    }
    // 金币
    if (cm.getMeso() < conds.meso) { cm.sendOk("金币不足"); cm.dispose(); return; }
    if (conds.cash > 0 && cm.getPlayer().getCashShop().getCash(1) < conds.cash) {
        cm.sendOk("点券不足"); cm.dispose(); return;
    }
    // 装备栏空间
    if (cm.getPlayer().getInventory(InventoryType.EQUIP).getNumFreeSlot() < 1) {
        cm.sendOk("装备栏至少需要1个空位"); cm.dispose(); return;
    }

    var ii = ItemInformationProvider.getInstance();
    var newWeapon = ii.getEquipById(targetId);
    if (!newWeapon) { cm.sendOk("目标武器资源不存在"); cm.dispose(); return; }

    // 继承属性
    if (prevId > 0) {
        var inv = cm.getPlayer().getInventory(InventoryType.EQUIP);
        var prevItem = inv.findById(prevId);
        if (!prevItem) {
            cm.sendOk("装备栏中未找到 #v" + prevId + "# #z" + prevId + "#"); cm.dispose(); return;
        }
        var template = ii.getEquipById(prevId);
        inheritEquip(prevItem, template, newWeapon);
        InventoryManipulator.removeFromSlot(cm.getPlayer().getClient(), InventoryType.EQUIP, prevItem.getPosition(), 1, false);
    }

    // 扣装备献祭
    consumeSacrifice(conds.equipSacrifice);
    // 扣材料/金币/点券
    deductCosts(conds);
    // 发放新武器
    cm.gainEquip(newWeapon);
    cm.saveOrUpdateCharacterExtendValue(STAGE_KEY_PREFIX + "weapon", String(targetIdx));
    cm.sendOk("武器升级成功！\r\n\r\n#b#v" + targetId + "# #z" + targetId + "##k");
    cm.dispose();
}

// ============================================================================
// 预览
// ============================================================================
function showPreviewMenu() {
    var jobIdx = getJobIndex();
    var branch = cm.getCharacterExtendValue(BRANCH_KEY) || "coatPants";
    var text = "\t\t\t\t#e#r装备升级路线预览#k#n\r\n\r\n";

    text += "#e防具路线（20阶段）：#n\r\n";
    for (var i = 0; i < ARMOR_STAGES.length; i++) {
        var ids = getArmorIds(i, branch);
        text += "#bLv" + ARMOR_STAGES[i].level + " " + ARMOR_STAGES[i].name + "#k ";
        for (var j = 0; j < ids.length; j++) text += "#v" + ids[j] + "#";
        text += "\r\n";
    }

    text += "\r\n#e武器路线（选择查看）：#n\r\n";
    var paths = WEAPON_PATHS[jobIdx];
    for (var p = 0; p < paths.length; p++) {
        text += "#L" + (400 + p) + "##b" + paths[p].name + "#k #v" + paths[p].items[0] + "# #z" + paths[p].items[0] + "##l\r\n";
    }
    cm.sendSimple(text);
}

function showWeaponPreview(pIdx) {
    var jobIdx = getJobIndex();
    var path = WEAPON_PATHS[jobIdx][pIdx];
    var text = "\t\t\t\t#e#r" + path.name + " 武器路线#k#n\r\n\r\n";
    for (var i = 0; i < path.items.length; i++) {
        text += "#bLv" + ARMOR_STAGES[i].level + " " + ARMOR_STAGES[i].name + "#k  #v" + path.items[i] + "# #z" + path.items[i] + "#\r\n";
    }
    cm.sendOk(text); cm.dispose();
}

// ============================================================================
// 工具函数
// ============================================================================
function getStage(type) {
    return parseInt(cm.getCharacterExtendValue(STAGE_KEY_PREFIX + type) || "-1", 10);
}

function getJobIndex() {
    var style = Job.getJobStyleInternal(cm.getPlayer().getJob().getId(), 0);
    var niche = style.getJobNiche();
    return niche >= 1 && niche <= 5 ? niche - 1 : -1;
}

function getArmorIds(stageIdx, branch) {
    var stg = ARMOR_STAGES[stageIdx];
    var ids = [stg.shared.cap];
    if (branch === "longcoat") ids.push(stg.branches.longcoat.longcoat);
    else ids.push(stg.branches.coatPants.coat, stg.branches.coatPants.pants);
    ids.push(stg.shared.glove, stg.shared.shoes, stg.shared.cape);
    return ids;
}

function hasBossClear(mobId) {
    return cm.getCharacterExtendValue(BOSS_KEY_PREFIX + mobId) === "1";
}

function consumeSacrifice(sacrifices) {
    if (!sacrifices || sacrifices.length === 0) return true;
    var inv = cm.getPlayer().getInventory(InventoryType.EQUIP);
    var ii = ItemInformationProvider.getInstance();
    for (var s = 0; s < sacrifices.length; s++) {
        var sac = sacrifices[s];
        var found = [];
        var iter = inv.list().iterator();
        while (iter.hasNext()) {
            var item = iter.next();
            if (found.length >= sac.count) break;
            var tpl = ii.getEquipById(item.getItemId());
            if (!tpl) continue;
            var slot = slotType(item.getItemId());
            if (sac.slot === "any" || sac.slot === slot) found.push(item);
        }
        if (found.length < sac.count) return false;
        for (var c = 0; c < sac.count; c++) {
            InventoryManipulator.removeFromSlot(cm.getPlayer().getClient(), InventoryType.EQUIP, found[c].getPosition(), 1, false);
        }
    }
    return true;
}

function consumePrevArmor(prevStage, branch) {
    var ids = getArmorIds(prevStage, branch);
    var inv = cm.getPlayer().getInventory(InventoryType.EQUIP);
    for (var i = 0; i < ids.length; i++) {
        var item = inv.findById(ids[i]);
        if (item) InventoryManipulator.removeFromSlot(cm.getPlayer().getClient(), InventoryType.EQUIP, item.getPosition(), 1, false);
    }
}

function deductCosts(conds) {
    for (var i = 0; i < conds.items.length; i++) cm.gainItem(conds.items[i][0], -conds.items[i][1]);
    if (conds.meso > 0) cm.gainMeso(-conds.meso);
    if (conds.cash > 0) cm.getPlayer().getCashShop().gainCash(1, -conds.cash);
}

function slotType(id) {
    var p = Math.floor(id / 10000);
    if (p === 100) return "cap";
    if (p === 104 || p === 105) return "coat";
    if (p === 106) return "pants";
    if (p === 107) return "shoes";
    if (p === 108) return "glove";
    if (p === 110) return "cape";
    if (p >= 130 && p <= 170) return "weapon";
    return "unknown";
}

function inheritEquip(src, srcTpl, tgt) {
    var stats = ["Str","Dex","Int","Luk","Hp","Mp","Watk","Matk","Wdef","Mdef","Acc","Avoid","Hands","Speed","Jump","Vicious"];
    for (var i = 0; i < stats.length; i++) {
        var n = stats[i];
        tgt["set" + n](clamp(tgt["get" + n]() + src["get" + n]() - srcTpl["get" + n]()));
    }
    tgt.setUpgradeSlots(Math.max(0, tgt.getUpgradeSlots() + src.getUpgradeSlots() - srcTpl.getUpgradeSlots()));
    tgt.setLevel(src.getLevel());
    tgt.setItemLevel(src.getItemLevel());
    tgt.setItemExp(src.getItemExp());
    tgt.setOwner(src.getOwner());
    tgt.setFlag(src.getFlag());
    tgt.setExpiration(src.getExpiration());
    tgt.setGiftFrom(src.getGiftFrom());
    tgt.setUpgradeHistory(src.getUpgradeHistory());
    tgt.setChaosHistory(src.getChaosHistory());
    tgt.setAbsorbHistory(src.getAbsorbHistory());
    tgt.setCombinationType(src.getCombinationType());
    tgt.setExpandAttribute1(src.getExpandAttribute1());
    tgt.setExpandAttribute2(src.getExpandAttribute2());
    tgt.setExpandAttribute3(src.getExpandAttribute3());
    tgt.setExpandAttribute4(src.getExpandAttribute4());
    tgt.setMaxStar(Math.max(src.getMaxStar(), tgt.getMaxStar()));
    tgt.setStarLevel(src.getStarLevel());
    tgt.setStarCount(src.getStarCount());
    tgt.setUpgradeResetCount(src.getUpgradeResetCount());
    tgt.setUpgradeReturn(src.getUpgradeReturn());
}

function formatPreview(ids) {
    var t = "";
    for (var i = 0; i < ids.length; i++) {
        t += "#v" + ids[i] + "# #z" + ids[i] + "#";
        t += i % 2 === 1 || i === ids.length - 1 ? "\r\n" : "    ";
    }
    return t;
}

function clamp(v) { return Math.max(-32768, Math.min(32767, v)); }
function formatNum(v) { return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ","); }
