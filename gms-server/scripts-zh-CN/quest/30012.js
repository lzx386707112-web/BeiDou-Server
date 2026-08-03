var status = -1;

function start(mode, type, selection) {
    qm.forceStartQuest();
    qm.dispose();
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("北侧的封印也解开了吗？");
        } else if (status == 1) {
            qm.sendNextPrev("嗯，现在所有的封印守护者都消灭掉了。你的封印也应该已经解开了。");
        } else if (status == 2) {
            qm.sendOk("我说怎么感觉身体变轻了。束缚着身体的黑暗气息已经完全感觉不到了！封印好像已经完全解开了！");
            qm.forceStartQuest();
            qm.forceCompleteQuest(30012);
            qm.gainExp(886000);
            qm.dispose();
        }
    }
}