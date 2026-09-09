/**
 * 9071006 / extreme_welcome — Extreme door NPC in the Monster Park lobby.
 * The door portal only opens this NPC. Daily count is consumed after a successful warp.
 */

var DAILY_LIMIT = 2;
var DAILY_KEY = "MPARK_EXTREME";
var EXTREME_MAP = 951000300;
var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        if (cm.getMapId() != 951000000) {
            cm.sendOk("请从怪物公园大厅的 Extreme 门进入。");
            cm.dispose();
            return;
        }
        if (cm.getMap(EXTREME_MAP) == null) {
            cm.sendOk("Extreme 场地现在无法进入。");
            cm.dispose();
            return;
        }
        var remaining = remainingToday();
        if (remaining <= 0) {
            cm.sendOk("今日 Extreme 园区次数已经用完（" + DAILY_LIMIT + " 次）。");
            cm.dispose();
            return;
        }
        cm.sendYesNo("欢迎来到怪物公园 Extreme。今日剩余 #b" + remaining + "/" + DAILY_LIMIT + "#k 次。要进入 Extreme 场地吗？");
        return;
    }
    if (remainingToday() <= 0) {
        cm.sendOk("今日 Extreme 园区次数已经用完（" + DAILY_LIMIT + " 次）。");
        cm.dispose();
        return;
    }
    if (cm.getMap(EXTREME_MAP) == null) {
        cm.sendOk("Extreme 场地现在无法进入。");
        cm.dispose();
        return;
    }
    consumeToday();
    cm.warp(EXTREME_MAP, 0);
    cm.dispose();
}

function usedToday() {
    var raw = cm.getCharacterExtendValue(DAILY_KEY, true);
    if (raw == null || raw === "") {
        return 0;
    }
    return parseInt(raw, 10) || 0;
}

function remainingToday() {
    return Math.max(0, DAILY_LIMIT - usedToday());
}

function consumeToday() {
    cm.saveOrUpdateCharacterExtendValue(DAILY_KEY, String(usedToday() + 1), true);
}
