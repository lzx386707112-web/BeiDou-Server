var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("封印全部解开了，这下终于可以到外面去了！");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n(南哈特让我把世界树带到圣地去，该怎么办呢？她刚刚解开了封印，看她那么开心……)");
        } else if (status == 2) {
            qm.sendNextPrev("#b#h0#：#k\r\n祝贺你恢复了自由。但是……冒险岛联盟希望你到圣地去。");
        } else if (status == 3) {
            qm.sendNextPrev("圣地……？");
        } else if (status == 4) {
            qm.sendNextPrev("#b#h0#：#k\r\n嗯，因为有很多人都在打你的主意，在圣地有女皇和神兽的保护，应该会比较安全。但是选择权在你自己，不愿意的话，不去也可以。他们没有权利逼迫你做出选择。");
        } else if (status == 5) {
            qm.sendNextPrev("……你说的对，如果在外面乱走，我的力量也许会被邪恶的家伙夺走。冒险岛联盟的判断是正确的。虽然有点不太乐意，但是在力量完全恢复之前，我会待在圣地。");
        } else if (status == 6) {
            qm.sendNextPrev("#b#h0#：#k\r\n真的没关系吗？被关了这么久，你难道不想到外面的世界去看看吗？");
        } else if (status == 7) {
            qm.sendNextPrev("没关系。等力量完全恢复之后，再去享受自由也不迟。到了那时，想动坏主意的家伙，我一下子就能解决！");
        } else if (status == 8) {
            qm.sendNextPrev("#b#h0#：#k\r\n好的。那我们到圣地去吧。为了防止发生什么事，冒险骑士团会护送你过去。");
        } else if (status == 9) {
            qm.sendNext("#b#h0#：#k\r\n准备好了吗？那就出发吧！");
        } else if (status == 10) {
            qm.warp(130000000, 0);
            qm.forceStartQuest();
			qm.forceCompleteQuest(30013);
			qm.forceCompleteQuest(30008);
			qm.dropMessage(1, "任务完成");
			qm.gainItem(1142536,1);
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest();
    qm.dispose();
}