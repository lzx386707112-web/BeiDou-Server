/**
 * @description 副本相关制作
 * 9400263 杯尔加莫特  	NPC 9120027   爆 闪耀币 4001254
 * 9400270 杜纳斯	  	NPC 9120031   爆 4039015
 * 9400271 战舰 尼贝隆	NPC 9120039	  爆 4039019
 * 9400266 努克斯	    NPC 9120036	  爆 4039016
 * 9400294 再生杜纳斯  	NPC 9120047	  爆 4039018
 * 9400288 欧比啦	  	NPC 9120053	  爆 4039017
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[装备制作]#k系统#n\t\t\t\t\r\n";
var status = -1;
var i = 0;
var meso_id = 9999999;//金币
var cash_id = 9999998;//点卷
var 金币_icon = "#fUI/UIWindow.img/QuestIcon/7/0#";
var 选择的制作列表;
var 制作目标;
var isDebug = false;          // 调试模式开关
var goldScale = 10000;
var broadcastDefaultType = 1;
let selectedIndex = -1;       // 选中的索引
let 需要并被继承的装备 = null;      // 材料装备
var 披风选系列中 = false;     // 披风：先选系列再选具体配方
var 披风制作多一步 = false;   // 披风多一级菜单，确认制作与执行制作各延后一档
//4251200 4251201 4251202

/**
 * 须放装备栏第一格、制作后 replaceData 继承星级/道具等级/洗练历史的材料装备 ID。
 * 新增配方时只需在对应部位数组追加 id（与 needItems 里带「继承」提示的材料一致）。
 */
var 继承装备材料 = {
    帽子: [1004637],
    耳环: [1032060, 1032061, 1032101, 1032205, 1032206, 1032207, 1032208, 1032209],
    眼睛: [1022118, 1022123, 1022129],
    鞋子: [1072239, 1072732, 1072737],
    腰带: [1132115, 1132296, 1132211, 1132212, 1132213, 1132214],
    披风: [
        1102871, // 愤怒的扎昆披风
        1102471, 1102472, 1102473, 1102474, 1102475, // 诺巴材料：赫里希安精锐
        1102476, 1102477, 1102478, 1102479, 1102480  // 暴君材料：诺巴
    ]
};

var _继承装备材料索引 = null;

function buildInheritEquipIdIndex() {
    var index = {};
    for (var category in 继承装备材料) {
        if (!继承装备材料.hasOwnProperty(category)) {
            continue;
        }
        var ids = 继承装备材料[category];
        for (var i = 0; i < ids.length; i++) {
            index[ids[i]] = true;
        }
    }
    return index;
}

function isNeedEquip(id) {
    if (_继承装备材料索引 === null) {
        _继承装备材料索引 = buildInheritEquipIdIndex();
    }
    return !!_继承装备材料索引[id];
}

var 耳环 = [
    //耳环奖励
    {
        id: 1032060,
        tipType: 6,
        needItems: [
            {id: 4001198, qty: 2, tip: "（毒物森林副本获取）"},//阿尔泰碎片
            {id: meso_id, qty: 1000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1032061,
        tipType: 6,
        needItems: [
            {id: 4001198, qty: 3, tip: "（毒物森林副本获取）"},
            {id: 1032060, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 20000},
        ]
    },
    //闪耀的阿尔泰
    {
        id: 1032101,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 4, tip: "（毒物森林副本获取）"},
            {id: 1032061, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 3000},
            {id: cash_id, qty: 30000},
        ]
    },
    //神话耳环链（金币/点券在闪耀阿尔泰基础上逐级翻倍）
    {
        id: 1032205,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 5, tip: "（毒物森林副本获取）"},
            {id: 1032101, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1032206,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 6, tip: "（毒物森林副本获取）"},
            {id: 1032205, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1032207,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 7, tip: "（毒物森林副本获取）"},
            {id: 1032206, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1032208,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 8, tip: "（毒物森林副本获取）"},
            {id: 1032207, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1032209,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 9, tip: "（毒物森林副本获取）"},
            {id: 1032208, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1032219,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 10, tip: "（毒物森林副本获取）"},
            {id: 1032209, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

var 眼睛 = [
    //眼睛奖励
    {
        id: 1022118,
        tipType: 6,
        needItems: [
            {id: 4001246, qty: 2, tip: "（玩具副本获取）"},//温暖的阳光
            {id: meso_id, qty: 1000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1022123,
        tipType: 6,
        needItems: [
            {id: 4001246, qty: 3, tip: "（玩具副本获取）"},
            {id: 1022118, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 20000},
        ]
    },
    //精灵眼睛
    {
        id: 1022129,
        tipType: 3,
        needItems: [
            {id: 4001246, qty: 4, tip: "（玩具副本获取）"},
            {id: 1022123, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 3000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1022195,
        tipType: 3,
        needItems: [
            {id: 4001246, qty: 20, tip: "（玩具副本获取）"},
            {id: 1022129, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

var 鞋子 = [
    //黄丁鞋
    {
        id: 1072239,
        tipType: 6,
        needItems: [
            {id: 4032266, qty: 2, tip: "（海盗副本获取）"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1072344,
        tipType: 3,
        needItems: [
            {id: 4032266, qty: 5, tip: "（海盗副本获取）"},
            {id: 1072239, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 5000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1072732,
        tipType: 3,
        needItems: [
            {id: 4039015, qty: 1, tip: "（杜纳斯产出）"},
            {id: 1072239, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1072737,
        tipType: 3,
        needItems: [
            {id: 4039016, qty: 1, tip: "（努克斯产出）"},
            {id: 1072732, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1072743,
        tipType: 3,
        needItems: [
            {id: 4039017, qty: 1, tip: "（欧比啦产出）"},
            {id: 1072737, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

/**
 * 腰带：愤怒的扎昆 → 强韧意志（黄/绿/蓝/红/黑）。黑贺腰带须道场等方式获得，不可在此制作。
 * 需继承的上一级腰带放在装备栏第一格。
 */
var 腰带 = [
    {
        id: 1132296,
        tipType: 3,
        needItems: [
            {id: 1132115, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001083, qty: 1, tip: "（扎昆的象征）"},
            {id: 1003439, qty: 1, tip: "（粉色扎昆头盔）"},
            {id: 4001198, qty: 1, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 1, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 1, tip: "（海盗副本获取）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1132211,
        tipType: 3,
        needItems: [
            {id: 1132296, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001198, qty: 2, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 2, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 2, tip: "（海盗副本获取）"},
            {id: 4021009, qty: 10, tip: "（星石）"},
            {id: 4011007, qty: 10, tip: "（月石）"},
            {id: 4011008, qty: 10, tip: "（锂）"},
            {id: 1132009, qty: 1, tip: "（紫色曲奇腰带）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1132212,
        tipType: 3,
        needItems: [
            {id: 1132211, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001198, qty: 3, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 3, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 3, tip: "（海盗副本获取）"},
            {id: 4021009, qty: 20, tip: "（星石）"},
            {id: 4011007, qty: 20, tip: "（月石）"},
            {id: 4011008, qty: 20, tip: "（锂）"},
            {id: 1132007, qty: 1, tip: "（蓝色曲奇腰带）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1132213,
        tipType: 3,
        needItems: [
            {id: 1132212, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001198, qty: 4, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 4, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 4, tip: "（海盗副本获取）"},
            {id: 4021009, qty: 30, tip: "（星石）"},
            {id: 4011007, qty: 30, tip: "（月石）"},
            {id: 4011008, qty: 30, tip: "（锂）"},
            {id: 4250000, qty: 30, tip: "（下等钻石）"},
            {id: 4250100, qty: 30, tip: "（下等蓝宝石）"},
            {id: 4250200, qty: 30, tip: "（下等石榴石）"},
            {id: 4250300, qty: 30, tip: "（下等蛋白石）"},
            {id: 4250400, qty: 30, tip: "（下等紫水晶）"},
            {id: 4250500, qty: 30, tip: "（下等海蓝宝石）"},
            {id: 4250600, qty: 30, tip: "（下等黄晶）"},
            {id: 4250700, qty: 30, tip: "（下等祖母绿）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1132214,
        tipType: 3,
        needItems: [
            {id: 1132213, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001198, qty: 5, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 5, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 5, tip: "（海盗副本获取）"},
            {id: 4021009, qty: 40, tip: "（星石）"},
            {id: 4011007, qty: 40, tip: "（月石）"},
            {id: 4011008, qty: 40, tip: "（锂）"},
            {id: 4250001, qty: 5, tip: "（中等钻石）"},
            {id: 4250101, qty: 5, tip: "（中等蓝宝石）"},
            {id: 4250201, qty: 5, tip: "（中等石榴石）"},
            {id: 4250301, qty: 5, tip: "（中等蛋白石）"},
            {id: 4250401, qty: 5, tip: "（中等紫水晶）"},
            {id: 4250501, qty: 5, tip: "（中等海蓝宝石）"},
            {id: 4250601, qty: 5, tip: "（中等黄晶）"},
            {id: 4250701, qty: 5, tip: "（中等祖母绿）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1132215,
        tipType: 3,
        needItems: [
            {id: 1132214, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001198, qty: 6, tip: "（毒物森林副本获取）"},
            {id: 4001246, qty: 6, tip: "（玩具副本获取）"},
            {id: 4032266, qty: 6, tip: "（海盗副本获取）"},
            {id: 4021009, qty: 50, tip: "（星石）"},
            {id: 4011007, qty: 50, tip: "（月石）"},
            {id: 4011008, qty: 50, tip: "（锂）"},
            {id: 4260000, qty: 50, tip: "（下等怪物结晶C）"},
            {id: 4260001, qty: 50, tip: "（下等怪物结晶B）"},
            {id: 4260002, qty: 50, tip: "（下等怪物结晶A）"},
            {id: 4260003, qty: 50, tip: "（中等怪物结晶C）"},
            {id: 4260004, qty: 50, tip: "（中等怪物结晶B）"},
            {id: 4260005, qty: 50, tip: "（中等怪物结晶A）"},
            {id: 4260006, qty: 50, tip: "（高等怪物结晶C）"},
            {id: 4260007, qty: 50, tip: "（高等怪物结晶B）"},
            {id: 4260008, qty: 50, tip: "（高等怪物结晶A）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

/**
 * 披风三系列：精锐 / 诺巴 / 暴君。每系列内 5 职业平行；
 * 诺巴、暴君须继承同职业上一系列披风（装备栏第一格）。
 */
var 披风_赫里希安精锐 = [
    // 赫里希安精锐（系列首阶，无需继承披风）
    {
        id: 1102471,
        tipType: 3,
        needItems: [
            {id: 1102871, qty: 1, tip: "(愤怒的扎昆披风)"},
            {id: 4031901, qty: 50, tip: "(帕普拉特斯之发)"},
            {id: 4000141, qty: 10, tip: "(大老板的手提灯)"},
            {id: 4000384, qty: 10, tip: "(黑色精华)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102472,
        tipType: 3,
        needItems: [
            {id: 1102871, qty: 1, tip: "（愤怒的扎昆披风）"},
            {id: 4031901, qty: 50, tip: "(帕普拉特斯之发)"},
            {id: 4000141, qty: 10, tip: "(大老板的手提灯)"},
            {id: 4000384, qty: 10, tip: "(黑色精华)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102473,
        tipType: 3,
        needItems: [
            {id: 1102871, qty: 1, tip: "（愤怒的扎昆披风）"},
            {id: 4031901, qty: 50, tip: "(帕普拉特斯之发)"},
            {id: 4000141, qty: 10, tip: "(大老板的手提灯)"},
            {id: 4000384, qty: 10, tip: "(黑色精华)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102474,
        tipType: 3,
        needItems: [
            {id: 1102871, qty: 1, tip: "（愤怒的扎昆披风）"},
            {id: 4031901, qty: 50, tip: "(帕普拉特斯之发)"},
            {id: 4000141, qty: 10, tip: "(大老板的手提灯)"},
            {id: 4000384, qty: 10, tip: "(黑色精华)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102475,
        tipType: 3,
        needItems: [
            {id: 1102871, qty: 1, tip: "（愤怒的扎昆披风）"},
            {id: 4031901, qty: 50, tip: "(帕普拉特斯之发)"},
            {id: 4000141, qty: 10, tip: "(大老板的手提灯)"},
            {id: 4000384, qty: 10, tip: "(黑色精华)"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

var 披风_诺巴 = [
    // 诺巴（继承同职业赫里希安精锐）
    {
        id: 1102476,
        tipType: 3,
        needItems: [
            {id: 1102471, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001101, qty: 200, tip: "（月妙的年糕）"},
            {id: 4000175, qty: 10, tip: "（皮亚奴斯模型）"},
            {id: 1002926, qty: 1, tip: "（暴力熊帽）", altIds: [1003023, 1003024]},
            {id: 4001241, qty: 1, tip: "（暴力熊足）"},
            {id: 4001261, qty: 50, tip: "（蝙蝠魔的皮碎片）"},
            {id: 2040728, qty: 50, tip: "（蝙蝠魔的鞋子力量卷轴30%）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102477,
        tipType: 3,
        needItems: [
            {id: 1102472, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001101, qty: 200, tip: "（月妙的年糕）"},
            {id: 4000175, qty: 10, tip: "（皮亚奴斯模型）"},
            {id: 1002926, qty: 1, tip: "（暴力熊帽）", altIds: [1003023, 1003024]},
            {id: 4001241, qty: 1, tip: "（暴力熊足）"},
            {id: 4001261, qty: 50, tip: "（蝙蝠魔的皮碎片）"},
            {id: 2040729, qty: 50, tip: "（蝙蝠魔的鞋子智力卷轴30%）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102478,
        tipType: 3,
        needItems: [
            {id: 1102473, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001101, qty: 200, tip: "（月妙的年糕）"},
            {id: 4000175, qty: 10, tip: "（皮亚奴斯模型）"},
            {id: 1002926, qty: 1, tip: "（暴力熊帽）", altIds: [1003023, 1003024]},
            {id: 4001241, qty: 1, tip: "（暴力熊足）"},
            {id: 4001261, qty: 50, tip: "（蝙蝠魔的皮碎片）"},
            {id: 2040731, qty: 50, tip: "（蝙蝠魔的鞋子敏捷卷轴30%）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102479,
        tipType: 3,
        needItems: [
            {id: 1102474, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001101, qty: 200, tip: "（月妙的年糕）"},
            {id: 4000175, qty: 10, tip: "（皮亚奴斯模型）"},
            {id: 1002926, qty: 1, tip: "（暴力熊帽）", altIds: [1003023, 1003024]},
            {id: 4001241, qty: 1, tip: "（暴力熊足）"},
            {id: 4001261, qty: 50, tip: "（蝙蝠魔的皮碎片）"},
            {id: 2040730, qty: 50, tip: "（蝙蝠魔的鞋子幸运卷轴30%）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102480,
        tipType: 3,
        needItems: [
            {id: 1102475, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4001101, qty: 200, tip: "（月妙的年糕）"},
            {id: 4000175, qty: 10, tip: "（皮亚奴斯模型）"},
            {id: 1002926, qty: 1, tip: "（暴力熊帽）", altIds: [1003023, 1003024]},
            {id: 4001241, qty: 1, tip: "（暴力熊足）"},
            {id: 4001261, qty: 50, tip: "（蝙蝠魔的皮碎片）"},
            {id: 2040728, qty: 25, tip: "（蝙蝠魔的鞋子力量卷轴30%）"},
            {id: 2040731, qty: 25, tip: "（蝙蝠魔的鞋子敏捷卷轴30%）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

var 披风_暴君 = [
    // 暴君（继承同职业诺巴）
    {
        id: 1102481,
        tipType: 3,
        needItems: [
            {id: 1102476, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4031438, qty: 1, tip: "（老海盗的航海日记）"},
            {id: 4031437, qty: 1, tip: "（老海盗的箱子钥匙）"},
            {id: 4001158, qty: 1, tip: "（女神的羽毛）"},
            {id: 4001159, qty: 1, tip: "（蒙特鸠珠子）"},
            {id: 4001160, qty: 1, tip: "（卡帕莱特珠子）"},
            {id: 4001094, qty: 10, tip: "（九灵龙的蛋）"},
            {id: 4251201, qty: 1, tip: "（中等五彩水晶）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102482,
        tipType: 3,
        needItems: [
            {id: 1102477, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4031438, qty: 1, tip: "（老海盗的航海日记）"},
            {id: 4031437, qty: 1, tip: "（老海盗的箱子钥匙）"},
            {id: 4001158, qty: 1, tip: "（女神的羽毛）"},
            {id: 4001159, qty: 1, tip: "（蒙特鸠珠子）"},
            {id: 4001160, qty: 1, tip: "（卡帕莱特珠子）"},
            {id: 4001094, qty: 10, tip: "（九灵龙的蛋）"},
            {id: 4251201, qty: 1, tip: "（中等五彩水晶）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102483,
        tipType: 3,
        needItems: [
            {id: 1102478, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4031438, qty: 1, tip: "（老海盗的航海日记）"},
            {id: 4031437, qty: 1, tip: "（老海盗的箱子钥匙）"},
            {id: 4001158, qty: 1, tip: "（女神的羽毛）"},
            {id: 4001159, qty: 1, tip: "（蒙特鸠珠子）"},
            {id: 4001160, qty: 1, tip: "（卡帕莱特珠子）"},
            {id: 4001094, qty: 10, tip: "（九灵龙的蛋）"},
            {id: 4251201, qty: 1, tip: "（中等五彩水晶）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102484,
        tipType: 3,
        needItems: [
            {id: 1102479, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4031438, qty: 1, tip: "（老海盗的航海日记）"},
            {id: 4031437, qty: 1, tip: "（老海盗的箱子钥匙）"},
            {id: 4001158, qty: 1, tip: "（女神的羽毛）"},
            {id: 4001159, qty: 1, tip: "（蒙特鸠珠子）"},
            {id: 4001160, qty: 1, tip: "（卡帕莱特珠子）"},
            {id: 4001094, qty: 10, tip: "（九灵龙的蛋）"},
            {id: 4251201, qty: 1, tip: "（中等五彩水晶）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
    {
        id: 1102485,
        tipType: 3,
        needItems: [
            {id: 1102480, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 4031438, qty: 1, tip: "（老海盗的航海日记）"},
            {id: 4031437, qty: 1, tip: "（老海盗的箱子钥匙）"},
            {id: 4001158, qty: 1, tip: "（女神的羽毛）"},
            {id: 4001159, qty: 1, tip: "（蒙特鸠珠子）"},
            {id: 4001160, qty: 1, tip: "（卡帕莱特珠子）"},
            {id: 4001094, qty: 10, tip: "（九灵龙的蛋）"},
            {id: 4251201, qty: 1, tip: "（中等五彩水晶）"},
            {id: meso_id, qty: 6000},
            {id: cash_id, qty: 60000},
        ]
    },
];

var 帽子 = [
    //愤怒扎昆头盔
    {
        id: 1004637,
        tipType: 3,
        needItems: [
            {id: 1002357, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1002390, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1002430, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003112, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003439, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003854, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1004119, qty: 1, tip: "（扎昆副本产出）"},
            {id: meso_id, qty: 10000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1003621,
        tipType: 3,
        needItems: [
            {id: 1004637, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 1003450, qty: 1, tip: "（pb副本产出）"},
            {id: 4021010, qty: 50, tip: ""},
            {id: 4251202, qty: 1, tip: "（pb副本产出）"},
            {id: meso_id, qty: 30000},
            {id: cash_id, qty: 50000},
        ]
    }
];

function start() {
    披风选系列中 = false;
    披风制作多一步 = false;
    制作目标 = null;
    需要并被继承的装备 = null;
    action(1, 0, 0)
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        let text = OldTitle;
        text += " \r\n";
        text += "#r#L0#整套装备进化#l#k\t\r\n\r\n";
        text += "#b#L1#耳环#l\t\r\n\r\n";
        text += "#L2#眼睛#l\t\r\n\r\n";
        text += "#L3#鞋子#l\t\r\n\r\n";
        text += "#L4#帽子#l\t\r\n\r\n";
        text += "#L5#武器#l\t\r\n\r\n";
        text += "#L6#灵魂戒指#l\t\r\n\r\n";
        text += "#L11#苍穹霸主戒#l\t\r\n\r\n";
        text += "#L9#腰带#l\t\r\n\r\n";
        text += "#L7#披风#l\t\r\n\r\n";
        text += "#L10#项链制作#l\t\r\n\r\n";
        text += "\r\n\r\n\t#r以下还未实现#k\t\r\n\r\n";
        text += "#L8#手套#l\t\r\n\r\n";
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else if (status === 2) {
        if (披风选系列中) {
            披风选系列中 = false;
            switch (selection) {
                case 0:
                    选择的制作列表 = 披风_赫里希安精锐;
                    break;
                case 1:
                    选择的制作列表 = 披风_诺巴;
                    break;
                case 2:
                    选择的制作列表 = 披风_暴君;
                    break;
                default:
                    cm.sendOk("无效的选择");
                    cm.dispose();
                    return;
            }
            披风制作多一步 = true;
            展示物品制作列表();
            return;
        }
        确认制作(selection);
    } else if (status === 3) {
        if (披风制作多一步) {
            披风制作多一步 = false;
            确认制作(selection);
            return;
        }
        doCraftItem();
    } else if (status === 4) {
        doCraftItem();
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        case 0:
            openNpc("装备制作/套装进化");
            break;
        case 1:
            选择的制作列表 = 耳环;
            展示物品制作列表();
            break;
        case 2:
            选择的制作列表 = 眼睛;
            展示物品制作列表();
            break;
        case 3:
            选择的制作列表 = 鞋子;
            展示物品制作列表();
            break;
        case 4:
            选择的制作列表 = 帽子;
            展示物品制作列表();
            break;
        case 5:
            openNpc("装备制作/武器制作");
            break;
        case 6:
            openNpc("灵魂戒指升级");
            break;
        case 11:
            openNpc("苍穹霸主戒");
            break;
        case 7:
            披风选系列中 = true;
            展示披风系列菜单();
            break;
        case 9:
            选择的制作列表 = 腰带;
            展示物品制作列表();
            break;
        case 10:
            openNpc("装备制作/项链制作");
            break;
        case 11:
            openNpc("装备制作/装备制作补偿");
            break;
        default:
            cm.sendOk("#b瞎么？没看到上面上写的还未实现，你就等吧！");
            cm.dispose();
    }
}


function 展示披风系列菜单() {
    let text = OldTitle + "\r\n请选择披风系列：\r\n\r\n";
    text += "#L0##b赫里希安精锐#k#l\t（战士/法师/弓/飞侠/海盗）\r\n\r\n";
    text += "#L1##b诺巴#k#l\t（须继承同职业精锐披风）\r\n\r\n";
    text += "#L2##b暴君#k#l\t（须继承同职业诺巴披风）\r\n\r\n";
    cm.sendSimple(text);
}

function 展示物品制作列表() {
    //展示物品
    let text = OldTitle + "\r\n请选择要制作的物品：\r\n\r\n";
    选择的制作列表.forEach((item, index) => {
        // 拼接目标物品信息
        text += `#L${index}##b制作#v${item.id}# #z${item.id}##k\r\n`;
        text += "\r\n";
    });
    cm.sendSimple(text);
}


function 确认制作(index) {
    selectedIndex = index; // 记录选中索引
    const targetItem = 选择的制作列表[index];
    制作目标 = targetItem;
    if (!targetItem) {
        cm.sendOk("无效的选择");
        cm.dispose();
        return;
    }
    // 构建确认信息
    let confirmText = `确定要制作 #v${targetItem.id}# #r#z${targetItem.id}# #k吗？\r\n#b所需材料：#k\r\n`;
    targetItem.needItems.forEach(need => {
        if (need.id === meso_id) {
            confirmText += `\r\n${金币_icon} x ${获取金币显示(need.qty)}\r\n`; // 使用金币图标
        } else if (need.id === cash_id) {
            confirmText += `#b点券 x #k ${need.qty}\r\n`; // 使用点券相关图标
        } else {
            // 仅当need.tip存在且不为空时才拼接提示部分
            const tipText = need.tip ? `\t#b${need.tip}#k` : '';
            confirmText += `#i${need.id}# #t${need.id}# x ${need.qty}${tipText}\r\n`;
        }
    });
    cm.sendYesNo(confirmText);
}


// function 制作物品() {
//     const targetItem = 制作目标;
//     if (!targetItem) {
//         cm.sendOk("制作信息已过期，请重新选择");
//         cm.dispose();
//         return;
//     }
//
//     // 检查背包是否能容纳目标物品
//     if (!cm.canHold(targetItem.id, 1)) {
//         cm.sendOk("背包空间不足，无法制作");
//         cm.dispose();
//         return;
//     }
//
//     // 检查所需材料
//     const lackItems = [];
//     let canExchange = true;
//
//     targetItem.needItems.forEach(need => {
//         if (need.id === meso_id) {
//             // 检查金币
//             if (cm.getMeso() < 获取金币(need.qty)) {
//                 lackItems.push(`金币（缺少：${获取金币(need.qty) - cm.getMeso()}）`);
//                 canExchange = false;
//             }
//         } else if (need.id === cash_id) {
//             // 检查点券（参考Cash.txt中点券相关处理）
//             if (cm.getPlayer().getCashShop().getCash(1) < need.qty) {
//                 lackItems.push(`点券（缺少：${need.qty - cm.getPlayer().getCashShop().getCash(1)}）`);
//                 canExchange = false;
//             }
//         } else {
//             // 检查普通物品
//             if (cm.getItemQuantity(need.id) < need.qty) {
//                 lackItems.push(`#t${need.id}#（缺少：${need.qty - cm.getItemQuantity(need.id)}）`);
//                 canExchange = false;
//             }
//         }
//     });
//
//     if (!canExchange) {
//         cm.sendOk(`材料不足：\r\n${lackItems.join("\r\n")}`);
//         cm.dispose();
//         return;
//     }
//
//     // 扣除所需材料
//     targetItem.needItems.forEach(need => {
//         if (need.id === meso_id) {
//             cm.gainMeso(-获取金币(need.qty));
//         } else if (need.id === cash_id) {
//             cm.getPlayer().getCashShop().gainCash(1, -need.qty);
//         } else {
//             cm.gainItem(need.id, -need.qty);
//         }
//     });
//
//     // 给予目标物品
//     cm.gainItem(targetItem.id, 1);
//     cm.sendOk(`恭喜您,制作 #i${targetItem.id}# #t${targetItem.id}# 成功！`);
//     const tipType = targetItem.tipType || 6;
//     sendSuperMegaphone(cm.getPlayer(), tipType, "装备制作", `恭喜玩家${cm.getPlayer().getName()}成功制作出【${cm.getPlayer().getItemName(targetItem.id)}】!`);
//     cm.dispose();
// }
//
// function 获取金币(meso) {
//     return meso * 10000;
// }
//
// function 获取金币显示(meso) {
//     if (meso >= 10000) {
//         return `${meso / 10000}E\r\n`;
//     } else {
//         return `${meso}W\r\n`;
//     }
// }

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}

/**
 * 执行物品制作逻辑
 */
function doCraftItem() {
    if (!制作目标) {
        cm.sendOk("制作信息已过期，请重新选择！");
        cm.dispose();
        return;
    }

    const player = cm.getPlayer();
    // 检查背包是否能容纳目标物品
    if (!cm.canHold(制作目标.id, 1)) {
        cm.sendOk("背包空间不足或者您已有同类物品，无法制作！");
        cm.dispose();
        return;
    }

    // 调试模式跳过材料检查
    if (!isDebug) {
        // 第一步：全量检查材料是否满足（不扣除）
        const lackItems = [];
        const canCraft = checkAllMaterials(player, lackItems);

        // 材料不足则提示并终止
        if (!canCraft) {
            cm.sendOk(`材料不足：\r\n${lackItems.join("\r\n")}`);
            cm.dispose();
            return;
        }

        // 第二步：所有材料满足，统一扣除
        deductAllMaterials(player);
    } else {
        // 调试模式：仅获取武器材料，不扣除
        制作目标.needItems.forEach(need => {
            if (isNeedEquip(need.id)) {
                需要并被继承的装备 = player.getInventory(InventoryType.EQUIP).getItem(1);
            }
        });
    }
    获取新装备并继承属性(制作目标.id, 需要并被继承的装备)
    // 制作成功提示+广播
    cm.sendOk(`恭喜您，制作 #i${制作目标.id}# #t${制作目标.id}# 成功！`);
    const tipType = 制作目标.tipType || broadcastDefaultType;
    const itemName = player.getItemName(制作目标.id);
    player.sendBroadcast(
        tipType,
        "装备制作",
        `恭喜玩家${player.getName()}成功制作出【${itemName}】!`,
        true
    );

    cm.dispose();
}

const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
const CraftLog = Java.type('org.slf4j.LoggerFactory').getLogger('BeiDouCraft');

function 获取新装备并继承属性(targetId, needItem) {
    const player = cm.getPlayer();
    const newItem = cm.gainItem(targetId, 1);
    if (!newItem) {
        cm.sendOk("制作失败：无法生成目标物品！");
        cm.dispose();
        return;
    }
    newItem.setFlag(1); // 上锁
    const inherited = !!needItem;
    if (needItem) {
        newItem.replaceData(needItem);
        InventoryManipulator.removeFromSlot(
            player.getClient(),
            InventoryType.EQUIP,
            needItem.getPosition(),
            1,
            false
        );
    }
    player.forceUpdateItem(newItem);
    const histSize = newItem.getUpgradeHistoryDes ? newItem.getUpgradeHistoryDes().size() : -1;
    CraftLog.info("[装备制作] charId={} name={} targetItemId={} inherit={} sourceItemId={} starLevel={} itemLevel={} upgradeHistoryRows={}",
        player.getId(), player.getName(), targetId, inherited,
        inherited ? needItem.getItemId() : 0,
        newItem.getStarLevel ? newItem.getStarLevel() : 0,
        newItem.getItemLevel ? newItem.getItemLevel() : 0,
        histSize);
}

/**
 * 从 need 的主 id 和 altIds 中，找到背包里实际持有的那个 id
 * @param {object} need - needItems 中的一项，可能含 altIds: [id, ...]
 * @returns {number|null} 实际持有的材料 id，找不到返回 null
 */
function findMatchingMaterialId(need) {
    if (cm.getItemQuantity(need.id) >= need.qty) return need.id;
    if (need.altIds) {
        for (var i = 0; i < need.altIds.length; i++) {
            if (cm.getItemQuantity(need.altIds[i]) >= need.qty) return need.altIds[i];
        }
    }
    return null;
}

/**
 * 全量检查所有材料是否满足（仅检查，不扣除）
 * @param {object} player - 玩家对象
 * @param {array} lackItems - 缺失材料列表（输出参数）
 * @returns {boolean} 是否所有材料都满足
 */
function checkAllMaterials(player, lackItems) {
    let allSatisfied = true;

    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            // 检查金币
            const needMeso = getMesoValue(need.qty);
            if (cm.getMeso() < needMeso) {
                lackItems.push(`金币（缺少：${needMeso - cm.getMeso()}）`);
                allSatisfied = false;
            }
        } else if (need.id === cash_id) {
            // 检查点券
            const cash = player.getCashShop().getCash(1);
            if (cash < need.qty) {
                lackItems.push(`点券（缺少：${need.qty - cash}）`);
                allSatisfied = false;
            }
        } else {
            // 检查普通物品/武器材料
            if (isNeedEquip(need.id)) {
                需要并被继承的装备 = player.getInventory(InventoryType.EQUIP).getItem(1);
                if (!需要并被继承的装备 || 需要并被继承的装备.getItemId() !== need.id) {
                    lackItems.push(`#t${need.id}#必须放在装备栏第一格`);
                    allSatisfied = false;
                }
            } else {
                const matchedId = findMatchingMaterialId(need);
                if (matchedId === null) {
                    const displayName = need.altIds
                        ? `#t${need.id}# / #t${need.altIds[0]}# / ...`
                        : `#t${need.id}#`;
                    lackItems.push(`${displayName}（缺少：${need.qty}）`);
                    allSatisfied = false;
                }
            }
        }
    });

    return allSatisfied;
}

/**
 * 统一扣除所有材料（仅在全量检查通过后调用）
 * @param {object} player - 玩家对象
 */
function deductAllMaterials(player) {
    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            // 扣除金币
            const needMeso = getMesoValue(need.qty);
            cm.gainMeso(-needMeso);
        } else if (need.id === cash_id) {
            // 扣除点券
            player.getCashShop().gainCash(1, -need.qty);
        } else {
            // 扣除普通物品（武器材料在属性继承时移除，此处无需处理）
            if (!isNeedEquip(need.id)) {
                const matchedId = findMatchingMaterialId(need);
                if (matchedId !== null) {
                    cm.gainItem(matchedId, -need.qty);
                }
            }
        }
    });
}

/**
 * 计算金币实际值（换算成游戏内单位）
 * @param {number} meso - 配置中的金币数量
 * @returns {number} 实际金币值
 */
function getMesoValue(meso) {
    return meso * goldScale;
}

/**
 * 格式化金币显示（W/E单位）
 * @param {number} meso - 配置中的金币数量
 * @returns {string} 格式化后的显示文本（无小数）
 */
function 获取金币显示(meso) {
    const realMeso = getMesoValue(meso); // 假设该函数已存在，返回正确的金币数值
    if (realMeso >= 100000000) {
        // 除以1亿后取整（推荐用Math.floor向下取整，也可换Math.round四舍五入）
        return `${Math.floor(realMeso / 100000000)}E`;
    } else if (realMeso >= 10000) {
        // 除以1万后取整
        return `${Math.floor(realMeso / 10000)}W`;
    } else {
        return `${realMeso}`;
    }
}
function sendSuperMegaphone(player, typeOrTitle, titleOrContent, content) {
    if (player.checkoutBroadcast()) {
        return;
    }
    var title = content === undefined ? typeOrTitle : titleOrContent;
    var message = content === undefined ? titleOrContent : content;
    var fullMessage = "[" + title + "] : " + message;
    var Server = Java.type("org.gms.net.server.Server");
    var PacketCreator = Java.type("org.gms.util.PacketCreator");

    // 5072000（高质地喇叭）使用类型 3 的全服喇叭封包。
    Server.getInstance().broadcastMessage(
        player.getWorld(),
        PacketCreator.serverNotice(
            3,
            player.getClient().getChannel(),
            player.getName() + " : " + fullMessage,
            true
        )
    );
}
