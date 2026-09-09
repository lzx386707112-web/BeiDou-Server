/**
 * 9071001 / Laku — Monster Park grocer.
 * TMS shop=1 with no Shop.wz dump; native shops only take mesos or Perfect Pitch.
 * All goods cost 4310020. Equip prices follow reqLevel against park coin rates
 * (1 / 5 / 20 / 50 per clear). Cubes are consumable, so they sit below same-tier gear.
 */

var COIN = 4310020;
var status = -1;
var category = -1;
var catalog = null;

var CATEGORIES = ["杂货", "魔方", "护肩", "心脏", "纹章", "徽章", "副刀"];

var STOCK = [
    [
        [2000000, 1],
        [2000001, 1],
        [2000002, 2],
        [2000003, 2],
        [2000006, 5],
        [2000016, 3],
        [2022000, 8],
        [2050004, 5],
        [2060000, 1],
        [2061000, 1],
        [2120000, 1]
    ],
    [
        [4007000, 90],
        [4007002, 135],
        [4007003, 165],
        [4007001, 210],
        [4007005, 255],
        [4007006, 300],
        [4007004, 360],
        [4007007, 450]
    ],
    [
        [1152000, 105],
        [1152010, 150],
        [1152018, 210],
        [1152191, 240],
        [1152022, 285],
        [1152030, 360],
        [1152038, 480],
        [1152108, 660],
        [1152174, 840],
        [1152212, 1200],
        [1152213, 1200],
        [1152214, 1200],
        [1152215, 1200],
        [1152216, 1200]
    ],
    [
        [1672008, 75],
        [1672000, 120],
        [1672003, 135],
        [1672027, 285],
        [1672040, 360],
        [1672076, 480],
        [1672069, 720],
        [1672092, 840]
    ],
    [
        [1190000, 225],
        [1190100, 225],
        [1190001, 420],
        [1190302, 720]
    ],
    [
        [1182000, 60],
        [1182002, 90],
        [1182274, 165],
        [1182066, 285],
        [1182076, 840]
    ],
    [
        [1342119, 105],
        [1342002, 150],
        [1342004, 210],
        [1342006, 285],
        [1342008, 360],
        [1342011, 480],
        [1342081, 720],
        [1342111, 1200],
        [1342121, 1200]
    ]
];

function start() {
    status = -1;
    category = -1;
    catalog = null;
    action(1, 0, 0);
}

function visibleStock(list) {
    var out = [];
    for (var i = 0; i < list.length; i++) {
        if (cm.canGenerateItem(list[i][0])) {
            out.push(list[i]);
        }
    }
    return out;
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        var owned = cm.getItemQuantity(COIN);
        var menu = "欢迎光临。这里用#b#t" + COIN + "##k换道具。你现在有 #b" + owned + "#k 枚。\r\n#b";
        for (var i = 0; i < CATEGORIES.length; i++) {
            menu += "#L" + i + "#" + CATEGORIES[i] + "#l\r\n";
        }
        cm.sendSimple(menu);
        return;
    }
    if (status == 1) {
        if (selection < 0 || selection >= STOCK.length) {
            cm.dispose();
            return;
        }
        category = selection;
        catalog = visibleStock(STOCK[category]);
        if (catalog.length == 0) {
            cm.sendOk("这一类暂时没有能兑换的道具。");
            cm.dispose();
            return;
        }
        var owned = cm.getItemQuantity(COIN);
        var menu = "#e" + CATEGORIES[category] + "#n  余额 #b" + owned + "#k 枚\r\n#b";
        for (var i = 0; i < catalog.length; i++) {
            menu += "#L" + i + "##v" + catalog[i][0] + "# #t" + catalog[i][0] + "#（" + catalog[i][1] + " 枚）#l\r\n";
        }
        cm.sendSimple(menu);
        return;
    }
    if (catalog == null || selection < 0 || selection >= catalog.length) {
        cm.dispose();
        return;
    }
    var itemId = catalog[selection][0];
    var cost = catalog[selection][1];
    if (!cm.canGenerateItem(itemId)) {
        cm.sendOk("该物品数据不存在，暂时无法兑换。");
        cm.dispose();
        return;
    }
    if (!cm.haveItem(COIN, cost)) {
        cm.sendOk("纪念币不够。需要 #b" + cost + "#k 枚。");
        cm.dispose();
        return;
    }
    if (!cm.canHold(itemId, 1)) {
        cm.sendOk("请先空出背包格子。");
        cm.dispose();
        return;
    }
    cm.gainItem(COIN, -cost);
    cm.gainItem(itemId, 1);
    cm.sendOk("谢谢惠顾。拿着#t" + itemId + "#小心点。");
    cm.dispose();
}
