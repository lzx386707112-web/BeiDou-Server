var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.sendOk("在你决定是否要进行这个任务之后再跟我说。如果你决定不做，你不会错过任何机会。");
        qm.dispose();
    } else {
        if (mode == 0 && type > 0 || selection == 1) {
            qm.sendOk("在你决定是否要进行这个任务之后再跟我说。如果你决定不做，你不会错过任何机会。");
            qm.dispose();
            return;
        }

        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
            qm.sendAcceptDecline("#b#h0##k！情况非常紧急，来不及解释了。请尽快去#b鲁塔比斯#k看看！");
        } else if (status == 1) {
            qm.sendOk("#b#h0##k，我会用神兽的力量立即把你传送过去。");
            qm.warp(910700200, 0);
            qm.forceStartQuest();
			qm.forceCompleteQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.dispose();
}
