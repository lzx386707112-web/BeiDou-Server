var status = -1;
var mode = 0;
var shopSelection = -1;

var VIRTUE_SHOP = [
    {item: 2049115, qty: 1, cost: 240, name: "Forward Chaos Scroll 50%"},
    {item: 2340000, qty: 1, cost: 360, name: "Blessing Scroll"}
];

var APPRENTICE_SHOP = [
    {item: 2003609, qty: 1, cost: 80, name: "EXP Potion"},
    {item: 4260010, qty: 10, cost: 60, name: "Enhancement Gem Fragment x10"},
    {item: 4260009, qty: 1, cost: 220, name: "Enhancement Gem"},
    {item: 4007000, qty: 1, cost: 180, name: "Cube"},
    {item: 4007002, qty: 1, cost: 260, name: "Super Cube"},
    {item: 4007003, qty: 1, cost: 320, name: "Star Cube"},
    {item: 2049115, qty: 1, cost: 560, name: "Forward Chaos Scroll 50%"},
    {item: 2340000, qty: 1, cost: 840, name: "Blessing Scroll"}
];

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(actionMode, type, selection) {
    if (actionMode == -1) {
        cm.dispose();
        return;
    }
    if (actionMode == 0 && type > 0) {
        cm.dispose();
        return;
    }
    if (actionMode == 1) {
        status++;
    } else {
        status--;
    }

    if (status == 0) {
        var text = "#e师徒系统#n\r\n\r\n";
        text += "#L0#查看我的师徒信息#l\r\n";
        text += "#L1#建立师徒关系#l\r\n";
        text += "#L2#领取阶段奖励#l\r\n";
        text += "#L3#领取本周历练池#l\r\n";
        text += "#L4#师德商店#l\r\n";
        text += "#L10#师徒商店#l\r\n";
        text += "#L5#报名 24 小时对决积分赛#l\r\n";
        text += "#L6#匹配对决积分赛#l\r\n";
        text += "#L7#查看我的对决状态#l\r\n";
        text += "#L8#查看排行榜#l\r\n";
        text += "#L9#解除当前师徒关系#l";
        cm.sendSimple(text);
        return;
    }

    if (status == 1) {
        mode = selection;
        if (mode == 0) {
            cm.sendOk(cm.mentorshipOverview());
            cm.dispose();
        } else if (mode == 1) {
            var menu = cm.mentorshipPartyMasterMenu();
            if (cm.mentorshipHasPartyMasterCandidate()) {
                cm.sendSimple(menu);
            } else {
                cm.sendOk(menu);
                cm.dispose();
            }
        } else if (mode == 2) {
            cm.sendOk(cm.mentorshipClaimStages());
            cm.dispose();
        } else if (mode == 3) {
            cm.sendOk(cm.mentorshipClaimWeekly());
            cm.dispose();
        } else if (mode == 4) {
            sendShop(VIRTUE_SHOP, "师德商店", "师德币", cm.mentorshipVirtueCoins());
        } else if (mode == 10) {
            sendShop(APPRENTICE_SHOP, "师徒商店", "师徒币", cm.mentorshipApprenticeCoins());
        } else if (mode == 5) {
            cm.sendGetNumber("请输入本次对决下注的师德币数量。", 100, 100, 1000000);
        } else if (mode == 6) {
            cm.sendGetNumber("请输入你愿意匹配的最高下注师德币数量。", 100, 100, 1000000);
        } else if (mode == 7) {
            cm.sendOk(cm.mentorshipDuelStatus());
            cm.dispose();
        } else if (mode == 8) {
            cm.sendSimple("#e排行榜#n\r\n\r\n#L0#本周师徒榜#l\r\n#L1#累计师徒榜#l");
        } else if (mode == 9) {
            cm.sendYesNo("确定要解除当前进行中的师徒关系吗？");
        }
        return;
    }

    if (status == 2) {
        if (mode == 1) {
            cm.sendOk(cm.mentorshipCreateFromParty(selection));
            cm.dispose();
        } else if (mode == 4 || mode == 10) {
            shopSelection = selection;
            var shop = getCurrentShop();
            if (shopSelection < 0 || shopSelection >= shop.length) {
                cm.dispose();
                return;
            }
            var item = shop[shopSelection];
            var coinName = getCurrentCoinName();
            var balance = mode == 4 ? cm.mentorshipVirtueCoins() : cm.mentorshipApprenticeCoins();
            cm.sendYesNo("确定使用 #r" + item.cost + "#k 枚" + coinName + "兑换 #b" + item.name + "#k x " + item.qty + " 吗？\r\n\r\n当前" + coinName + "：#b" + balance + "#k");
        } else if (mode == 5) {
            cm.sendOk(cm.mentorshipStartDuel(selection));
            cm.dispose();
        } else if (mode == 6) {
            cm.sendOk(cm.mentorshipJoinDuel(selection));
            cm.dispose();
        } else if (mode == 8) {
            cm.sendOk(cm.mentorshipRanking(selection == 0 ? "weekly" : "total"));
            cm.dispose();
        } else if (mode == 9) {
            cm.sendOk(cm.mentorshipCancel());
            cm.dispose();
        }
        return;
    }

    if (status == 3) {
        if (mode == 4 || mode == 10) {
            buyShopItem(shopSelection);
        }
        cm.dispose();
    }
}

function sendShop(shop, title, coinName, balance) {
    var text = "#e" + title + "#n\r\n当前" + coinName + "：#b" + balance + "#k\r\n\r\n";
    for (var i = 0; i < shop.length; i++) {
        var item = shop[i];
        if (cm.canGenerateItem(item.item)) {
            text += "#L" + i + "##v" + item.item + "# " + item.name + " x " + item.qty + " - #r" + item.cost + "#k " + coinName + "#l\r\n";
        }
    }
    cm.sendSimple(text);
}

function buyShopItem(index) {
    var shop = getCurrentShop();
    if (index < 0 || index >= shop.length) {
        cm.sendOk("兑换项目不存在。");
        return;
    }
    var item = shop[index];
    if (!cm.canGenerateItem(item.item)) {
        cm.sendOk("该物品数据不存在，暂时无法兑换。");
        return;
    }
    if (!cm.canHold(item.item, item.qty)) {
        cm.sendOk("请先整理背包空间。");
        return;
    }
    var paid = mode == 4 ? cm.mentorshipSpendVirtue(item.cost) : cm.mentorshipSpendApprentice(item.cost);
    if (!paid) {
        cm.sendOk(getCurrentCoinName() + "不足。");
        return;
    }
    cm.gainItem(item.item, item.qty);
    cm.sendOk("兑换成功，获得 #b" + item.name + "#k x " + item.qty + "。");
}

function getCurrentShop() {
    return mode == 4 ? VIRTUE_SHOP : APPRENTICE_SHOP;
}

function getCurrentCoinName() {
    return mode == 4 ? "师德币" : "师徒币";
}
