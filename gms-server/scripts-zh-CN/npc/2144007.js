var status = -1;
var selectionLog = [];

function start() {
    action(1, 0, 0)
}

function action(d, c, b) {
    if (status == 0 && d == 0) {
        cm.dispose();
        return
    }
    (d == 1) ? status++ : status--;
    selectionLog[status] = b;
    var a = -1;
    if (status <= a++) {
        cm.dispose()
    } else {
        if (status === a++) {
            if (!cm.isQuestActive(31173) || cm.haveItem(4033081, 1)) {
                cm.dispose();
                return
            }
            cm.gainItem(4033081, 1);
            cm.sendNext("蛋好像没事。请好好照看，不要让蛋受伤。");
            cm.forceStartQuest(31184)
        } else {
            cm.dispose()
        }
    }
}
