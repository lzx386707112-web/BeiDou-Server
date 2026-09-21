var status = -1;
var stage = "main";
var selectedExchange = -1;

var AREA_ID = 32010;
var DENARO = 4310100;
var Short = Java.type("java.lang.Short");
var exchanges = [
    { item: 1012438, price: 160, name: "漩涡文身" },
    { item: 1022211, price: 160, name: "漩涡眼镜" },
    { item: 1032224, price: 180, name: "漩涡耳环" },
    { item: 1122269, price: 200, name: "漩涡吊坠" },
    { item: 1132247, price: 180, name: "漩涡腰带" },
    { item: 1003976, price: 250, name: "漩涡帽子" },
    { item: 1052669, price: 350, name: "漩涡皇家外套" },
    { item: 1082556, price: 250, name: "漩涡手套" },
    { item: 1072870, price: 250, name: "漩涡鞋" },
    { item: 1102623, price: 250, name: "漩涡披风" },
    { item: 1302297, price: 400, name: "漩涡剑" },
    { item: 1312173, price: 400, name: "漩涡斧" },
    { item: 1322223, price: 400, name: "漩涡锤" },
    { item: 1332247, price: 400, name: "漩涡匕首" },
    { item: 1372195, price: 400, name: "漩涡短杖" },
    { item: 1382231, price: 400, name: "漩涡长杖" },
    { item: 1402220, price: 400, name: "漩涡双手剑" },
    { item: 1412152, price: 400, name: "漩涡双手战斧" },
    { item: 1422158, price: 400, name: "漩涡巨锤" },
    { item: 1432187, price: 400, name: "漩涡矛" },
    { item: 1442242, price: 400, name: "漩涡戟" },
    { item: 1452226, price: 400, name: "漩涡弓" },
    { item: 1462213, price: 400, name: "漩涡弩" },
    { item: 1472235, price: 400, name: "漩涡拳甲" },
    { item: 1482189, price: 400, name: "漩涡冲拳" },
    { item: 1492199, price: 400, name: "漩涡手铳" }
];

function start() {
    status = -1;
    action(1, 0, 0);
}

function stateKey() {
    return Short.valueOf(String(AREA_ID));
}

function intValue(value, fallback) {
    var parsed = parseInt(value);
    return isNaN(parsed) ? fallback : parsed;
}

function loadState() {
    var raw = cm.getPlayer().getAreaInfos().get(stateKey());
    if (raw == null) return null;
    var p = String(raw).split("|");
    if (p.length < 21 || p[0] != "C1") return null;
    return {
        parts: p,
        level: Math.max(1, Math.min(10, intValue(p[3], 1))),
        exp: Math.max(0, intValue(p[4], 0)),
        pendingCoins: Math.max(0, intValue(p[12], 0)),
        pendingExp: Math.max(0, intValue(p[13], 0)),
        pendingItem: Math.max(0, intValue(p[14], 0)),
        pendingItemQty: Math.max(0, intValue(p[15], 0))
    };
}

function saveState(s) {
    s.parts[3] = String(s.level);
    s.parts[4] = String(s.exp);
    s.parts[12] = String(s.pendingCoins);
    s.parts[13] = String(s.pendingExp);
    s.parts[14] = String(s.pendingItem);
    s.parts[15] = String(s.pendingItemQty);
    cm.getPlayer().getAreaInfos().put(stateKey(), s.parts.join("|"));
}

function hasPending(s) {
    return s != null && (s.pendingCoins > 0 || s.pendingExp > 0 || s.pendingItem > 0);
}

function showMain() {
    stage = "main";
    var s = loadState();
    var text = "#e凯梅尔兹金币交换所#n\r\n";
    text += "持有：#b" + cm.itemQuantity(DENARO) + " 枚凯梅尔兹金币#k\r\n\r\n";
    if (hasPending(s)) text += "#L0##r领取本次航海收益#k#l\r\n";
    text += "#L1##b兑换漩涡装备#k#l";
    cm.sendSimple(text);
}

function claimVoyage() {
    var s = loadState();
    if (!hasPending(s)) {
        cm.sendOk("目前没有待领取的航海收益。");
        cm.dispose();
        return;
    }
    if (s.pendingCoins > 0 && !cm.canHold(DENARO, s.pendingCoins)) {
        cm.sendOk("其他栏空间不足，无法领取凯梅尔兹金币。");
        cm.dispose();
        return;
    }
    if (s.pendingItem > 0 && !cm.canHold(s.pendingItem, s.pendingItemQty)) {
        cm.sendOk("装备栏空间不足，无法领取航海战利品。");
        cm.dispose();
        return;
    }

    var coins = s.pendingCoins;
    var gainedExp = s.pendingExp;
    var loot = s.pendingItem;
    var lootQty = s.pendingItemQty;
    if (coins > 0) cm.gainItem(DENARO, coins);
    if (loot > 0 && lootQty > 0) cm.gainItem(loot, lootQty);

    s.exp += gainedExp;
    var levelsGained = 0;
    while (s.level < 10 && s.exp >= 10000) {
        s.exp -= 10000;
        s.level++;
        levelsGained++;
    }
    if (s.level >= 10) s.exp = 0;
    s.pendingCoins = 0;
    s.pendingExp = 0;
    s.pendingItem = 0;
    s.pendingItemQty = 0;
    saveState(s);

    var text = "已领取 #b" + coins + " 枚凯梅尔兹金币#k，并获得 #b" + gainedExp + " 点舰船经验#k。";
    if (levelsGained > 0) text += "\r\n舰船提升了 #b" + levelsGained + "#k 级，当前 Lv." + s.level + "。";
    if (loot > 0) text += "\r\n额外战利品：#i" + loot + "# #z" + loot + "# x " + lootQty;
    cm.sendOk(text);
    cm.dispose();
}

function showExchange() {
    stage = "exchange";
    var text = "#e漩涡装备兑换#n\r\n持有：#b" + cm.itemQuantity(DENARO) + "#k 枚\r\n\r\n";
    for (var i = 0; i < exchanges.length; i++) {
        var offer = exchanges[i];
        text += "#L" + i + "##i" + offer.item + "# #b" + offer.name + "#k - #r" + offer.price + "#k 枚#l\r\n";
    }
    cm.sendSimple(text);
}

function exchangeItem(index) {
    if (index < 0 || index >= exchanges.length) {
        cm.dispose();
        return;
    }
    var offer = exchanges[index];
    if (!cm.haveItem(DENARO, offer.price)) {
        cm.sendOk("凯梅尔兹金币不足，需要 " + offer.price + " 枚。");
        cm.dispose();
        return;
    }
    if (!cm.canHold(offer.item, 1)) {
        cm.sendOk("装备栏空间不足。");
        cm.dispose();
        return;
    }
    cm.gainItem(DENARO, -offer.price);
    cm.gainItem(offer.item, 1);
    cm.sendOk("成功兑换 #i" + offer.item + "# #b" + offer.name + "#k。");
    cm.dispose();
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    if (status == -1) {
        status = 0;
        showMain();
        return;
    }
    if (stage == "main") {
        if (selection == 0) claimVoyage();
        else if (selection == 1) showExchange();
        else cm.dispose();
        return;
    }
    if (stage == "exchange") {
        selectedExchange = intValue(selection, -1);
        var offer = selectedExchange >= 0 && selectedExchange < exchanges.length ? exchanges[selectedExchange] : null;
        if (offer == null) {
            cm.dispose();
            return;
        }
        stage = "confirmExchange";
        cm.sendYesNo("使用 #r" + offer.price + " 枚凯梅尔兹金币#k兑换 #i" + offer.item + "# #b" + offer.name + "#k？");
        return;
    }
    if (stage == "confirmExchange") exchangeItem(selectedExchange);
}
