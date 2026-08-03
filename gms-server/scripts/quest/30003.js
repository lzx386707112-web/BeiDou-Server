var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0 || selection == 1) {
            qm.dispose();
            return;
        }
        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
            qm.sendNext("怎么才能从这里出去呢？");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n那边有个通往外面的出口。只要通过出口出去就行。");
        } else if (status == 2) {
            qm.sendNextPrev("我已经试过好几次了，但是没办法出去。");
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n没办法出去？出口堵住了吗？知道了，我去试试看。");
        } else if (status == 4) {
            qm.sendOk("快去帮我确认一下。我真的很想出去……");
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0 || selection == 1) {
            qm.dispose();
            return;
        }
        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
            qm.sendNext("确认了吗？");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n嗯，没问题，可以通往外面。");
        } else if (status == 2) {
            qm.sendOk("真的吗？看来只有我没办法出去……");
            qm.forceCompleteQuest();
            qm.dispose();
        }
    }
}
