var status = -1;
var selectedOption = -1;
var FEATURE_OPEN = false;

var HERO_COIN_ID = 4310060;
var HERO_COIN_MATERIALS = [4251200, 4251201, 4251202];

function start() {
    if (!FEATURE_OPEN) {
        cm.sendOk("暂未开放！");
        cm.dispose();
        return;
    }
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }

    status++;
    if (status === 0) {
        var menu = "#e#b五转女神#k#n\r\n\r\n";
        menu += "#L0##b领取五转技能#k#l\r\n";
        menu += "#L1##b合成英雄币#k#l";
        cm.sendSimple(menu);
        return;
    }

    if (status === 1) {
        selectedOption = selection;
        if (selectedOption === 0) {
            cm.dispose();
            cm.openNpc(9900008, "五转技能面板");
            return;
        }
        if (selectedOption === 1) {
            cm.sendYesNo(buildCraftPrompt());
            return;
        }
    }

    if (status === 2 && selectedOption === 1) {
        craftHeroCoin();
        return;
    }

    cm.dispose();
}

function buildCraftPrompt() {
    var text = "#e合成 #i" + HERO_COIN_ID + "# #b#t" + HERO_COIN_ID + "##k × 1#n\r\n\r\n";
    text += "需要以下材料：\r\n";
    for (var i = 0; i < HERO_COIN_MATERIALS.length; i++) {
        var itemId = HERO_COIN_MATERIALS[i];
        text += "#i" + itemId + "# #b#t" + itemId + "##k × 1";
        text += "  #d(持有 " + cm.itemQuantity(itemId) + ")#k\r\n";
    }
    text += "\r\n确定要合成吗？";
    return text;
}

function craftHeroCoin() {
    var missing = [];
    for (var i = 0; i < HERO_COIN_MATERIALS.length; i++) {
        var itemId = HERO_COIN_MATERIALS[i];
        if (!cm.haveItem(itemId, 1)) {
            missing.push("#i" + itemId + "# #t" + itemId + "# × 1");
        }
    }

    if (missing.length > 0) {
        cm.sendOk("材料不足：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }
    if (!cm.canHold(HERO_COIN_ID, 1)) {
        cm.sendOk("其他栏背包空间不足，请整理后再来。");
        cm.dispose();
        return;
    }

    for (var materialIndex = 0; materialIndex < HERO_COIN_MATERIALS.length; materialIndex++) {
        cm.gainItem(HERO_COIN_MATERIALS[materialIndex], -1);
    }
    cm.gainItem(HERO_COIN_ID, 1);
    cm.sendOk("合成成功，获得 #i" + HERO_COIN_ID + "# #b#t" + HERO_COIN_ID + "##k × 1。");
    cm.dispose();
}
