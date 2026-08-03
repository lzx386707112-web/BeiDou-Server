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
            qm.sendNext("确认了吗？");
        } else if (status == 1) {
            qm.sendNextPrev("这次的卷轴也什么问题都没有。");
        } else if (status == 2) {
            qm.sendOk("这次又失败了……我真的没办法出去吗……？");
            qm.forceCompleteQuest(30004);
            qm.dispose();
        }
    }
}