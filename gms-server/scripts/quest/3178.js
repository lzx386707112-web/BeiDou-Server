var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        qm.sendNext("请走只有国王和王后才知道的密道，把我的吊坠带到接见室去。");
    } else {
        qm.forceStartQuest();
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 0 && type > 0) {
        qm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }
    if (status == 0) {
        if (!qm.haveItem(4032839, 1)) {
            qm.sendOk("还没有把吊坠带回来。");
            qm.dispose();
            return;
        }
        qm.forceCompleteQuest();
        qm.dispose();
    }
}
