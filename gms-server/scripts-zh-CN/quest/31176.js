var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) {
            status++;
        } else {
            status--;
        }
        if (status == 0) {
            qm.sendNext("原来在这里啊。让我找了好久。我从克洛乌那里收到了报告，说#h0#你救了谢丽尔。")
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n那是必须要做的事情。对了，阿卡伊勒好像到封印黑魔法师的过去的时间神殿去了。")
        } else if (status == 2) {
            qm.sendNextPrev("是吗？……已经找到阿卡伊勒的痕迹了吗……比我预想的还要快。")
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n……格莱特？")
        } else if (status == 4) {
            qm.sendOk("呵呵，我不能让你这样卑贱的东西跟在阿卡伊勒后面。这里将是你的坟墓！");
            qm.forceStartQuest();
            qm.forceStartQuest(31187, 1);
            qm.spawnMonster(9300487, 345, 2);
            qm.dispose()
        }
    }
}

function stage0(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.sendOk("那就等你准备好了再来找我吧。");
            qm.dispose();
            return;
        }
        if (mode == 1) {
            status++;
        } else {
            status--;
        }
        if (status == 0) {
            var e = qm.getQuest();
            qm.sendYesNo("这个任务的依次对话脚本还没有修复哦。它的脚本位于： #b %SCRIPT_PATH%#k\r\n\r\n如果你有兴趣，欢迎一起来修复！\r\n\r\n那么现在，你要立刻开始这个任务吗？")
        } else if (status == 1) {
            qm.forceStartQuest();
            qm.dispose()
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
            qm.sendNext("谢谢你。你能把我们最后的孩子交给我吗？")
        } else if (status == 1) {
            qm.sendOk("等弗里德醒来之后，我会让他带着蛋到安全的地方去。虽然对弗里德非常抱歉，但这是朋友的委托，他一定会用一生去保护他的。这样，我们的希望就能延续到未来。");
            qm.forceCompleteQuest();
            qm.dispose()
        }
    }
}
