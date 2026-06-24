var status = -1;

var START_ID = 1118000;
var RING_COUNT = 43;
var SELECT_ALL = 9999;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (!checkStatus(mode)) {
        return;
    }

    if (status == 0) {
        cm.sendSimple(buildMenu());
    } else if (status == 1) {
        if (selection == SELECT_ALL) {
            gainAllRings();
        } else {
            gainOneRing(selection);
        }
    } else {
        cm.dispose();
    }
}

function buildMenu() {
    var text = "#e灵魂戒指领取#n\r\n\r\n";
    text += "#r领取全部需要装备栏至少 " + RING_COUNT + " 个空格。#k\r\n\r\n";
    text += "#L" + SELECT_ALL + "##b领取全部灵魂戒指1-" + RING_COUNT + "#k#l\r\n\r\n";

    for (var i = 0; i < RING_COUNT; i++) {
        var itemId = START_ID + i;
        text += "#L" + i + "##v" + itemId + "##t" + itemId + "##l\r\n";
    }

    return text;
}

function gainAllRings() {
    if (cm.isNotCanHold(1, RING_COUNT)) {
        return;
    }

    for (var i = 0; i < RING_COUNT; i++) {
        cm.gainItem(START_ID + i, 1);
    }

    cm.sendOk("领取成功，已获得灵魂戒指1-" + RING_COUNT + "。");
    cm.dispose();
}

function gainOneRing(selection) {
    if (selection < 0 || selection >= RING_COUNT) {
        cm.sendOk("选择错误。");
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
    cm.sendOk("领取成功，已获得 #v" + itemId + "##t" + itemId + "#。");
    cm.dispose();
}

function checkStatus(mode) {
    if (mode == -1) {
        cm.dispose();
        return false;
    }

    if (mode == 1) {
        status++;
    } else {
        status--;
    }

    if (status == -1) {
        cm.dispose();
        return false;
    }

    return true;
}
