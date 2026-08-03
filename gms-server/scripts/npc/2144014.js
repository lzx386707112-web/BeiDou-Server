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
            if (!cm.isQuestActive(31174) || !cm.haveItem(4033082, 1)) {
                cm.dispose();
                return
            }
            cm.gainItem(4033082, -1);
            cm.sendNext("(突然开始发光，双弩精灵的表情好像变好了。这样就行了吗？)")
        } else {
            cm.dispose();
            cm.sendOk("这样一来，英雄们的安全就都有了保障。这全都是多亏了你。但还有一点让我放心不下，希望你重新和我说话。");
            cm.forceCompleteQuest(31174)
        }
    }
}
