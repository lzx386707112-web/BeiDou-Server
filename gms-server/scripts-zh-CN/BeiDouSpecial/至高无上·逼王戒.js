var status = -1;

var START_ID = 1118063;
var RING_COUNT = 16;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }

    status++;
    if (status == 0) {
        cm.sendSimple(buildMenu());
    } else if (status == 1) {
        gainRing(selection);
    } else {
        cm.dispose();
    }
}

function buildMenu() {
    var text = "#e至高无上·逼王戒领取#n\r\n\r\n";
    text += "请选择想要领取的特效款：\r\n\r\n";

    for (var i = 0; i < RING_COUNT; i++) {
        var itemId = START_ID + i;
        text += "#L" + i + "##v" + itemId + "##t" + itemId + "#（特效款 " + (i + 1) + "）#l\r\n";
    }

    return text;
}

function gainRing(selection) {
    if (selection < 0 || selection >= RING_COUNT) {
        cm.sendOk("选择无效，请重新打开对话。");
        cm.dispose();
        return;
    }

    var itemId = START_ID + selection;
    if (!cm.canHold(itemId, 1)) {
        cm.sendOk("装备栏空间不足，请整理后再领取。");
        cm.dispose();
        return;
    }

    cm.gainItem(itemId, 1);
    cm.sendOk("领取成功，已获得 #v" + itemId + "##t" + itemId + "#（特效款 " + (selection + 1) + "）。");
    cm.dispose();
}
