var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.sendOk("看来你还没有准备好帮助她。等你想好了再来吧。");
            qm.dispose();
            return;
        }
        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
            qm.sendNext("我想离开这里。");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n你说什么。");
        } else if (status == 2) {
            qm.sendNextPrev("我想从这里出去。");
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n你到底在说什么啊？这是什么地方？你是谁？");
        } else if (status == 4) {
            qm.sendNextPrev("这里？这里是鲁塔比斯。我想离开这里。请你帮帮我。");
        } else if (status == 5) {
            qm.sendNextPrev("#b#h0#：#k\r\n(唉……一直在自言自语。真费劲。)");
        } else if (status == 6) {
            qm.sendYesNo("#b#h0#：#k\r\n(看来她好像是迷路了，要帮帮她吗？)");
        } else if (status == 7) {
            qm.sendNext("#b#h0#：#k\r\n知道了。我来看看有没有办法离开这里。");
        } else if (status == 8) {
            qm.sendNextPrev("你真的愿意帮我吗？不许骗我哦！");
        } else if (status == 9) {
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) {
            status++;
        } else {
            status--;
        }
        if (status == 0) {
            qm.sendOk("你找到离开这里的办法了吗？");
            qm.forceCompleteQuest();
            qm.dispose();
        }
    }
}
