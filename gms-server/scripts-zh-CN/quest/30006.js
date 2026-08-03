var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) status++; else status--;
        if (status == 0) {
			qm.sendNextPrev("#b#h0#：#k\r\n......");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n为了解开你的封印，必须先了解入侵者的身份。");
        } else if (status == 2) {
            qm.sendNextPrev("但是他们已经全部走掉了。");
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n也许会留下什么线索，让我们找找看吧。对于那边的四扇门，你知道些什么吗？");
        } else if (status == 4) {
            qm.sendNextPrev("把我封印起来的那些人制造了那些门之后就走了。我试着到门外去，但是因为封印的原因，没办法出去。");
        } else if (status == 5) {
            qm.sendNextPrev("#b#h0#：#k\r\n那些门的外面会不会有什么线索呢？到门外面去……嗯？这是怎么回事？");
        } else if (status == 6) {
            qm.sendNextPrev("哇，你的身体发出了白光！");
        } else if (status == 7) {
            qm.sendNextPrev("#b#h0#：#k\r\n这到底是怎么回事？嗯，嗯？身...身体被吸进去了！");
        } else if (status == 8) {
            qm.sendNextPrev("#b#h0##k！！！");
        } else if (status == 9) {
            qm.sendOk("#b#h0##k！！！");
            qm.forceStartQuest();
            qm.warp(910700300, 0);
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest();
    qm.dispose();
}