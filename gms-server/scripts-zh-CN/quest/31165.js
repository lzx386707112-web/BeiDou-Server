var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.sendOk("那就等你准备好了再来找我吧。");
            qm.dispose();
            return;
        }
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("在#b三个门#k出现了裂缝。解谜的时间到了。阿卡伊勒、时空门、时间神殿的裂缝……");
        } else if (status == 1) {
            qm.sendNextPrev("俗话说不入虎穴，焉得虎子。要想解开所有的问题，必须直接进入裂缝内部。");
        } else if (status == 2) {
            qm.sendYesNo("克洛乌和谢丽尔已经在做准备了。你做好执行新任务的准备了吗？");
        } else if (status == 3) {
            qm.sendOk("请确认一下裂缝里面有什么东西。如果在裂缝里遇到了阿卡伊勒……啊，没什么。请通过#b时间神殿三个门#k的裂缝进去，千万小心。");
            qm.forceStartQuest();
            qm.dispose();
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
        if (mode == 1) status++; else status--;
        if (status == 0) {
            var e = qm.getQuest();
            qm.sendYesNo("这个任务的依次对话脚本还没有修复哦。它的脚本位于： #b %SCRIPT_PATH%#k\r\n\r\n如果你有兴趣，欢迎一起来修复！\r\n\r\n那么现在，你要立刻开始这个任务吗？");
        } else if (status == 1) {
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.sendOk("那就等你准备好了再来找我吧。");
            qm.dispose();
            return;
        }
        if (mode == 1) status++; else status--;
        if (status == 0) {
            var e = qm.getQuest();
            qm.sendYesNo("这个任务的结束脚本还没有修复哦。它的脚本位于： #b /脚本/任务/#e" + e + "#n.js#k\r\n\r\n如果你有兴趣，欢迎一起来修复！\r\n\r\n那么现在，你要立刻完成这个任务吗？");
        } else if (status == 1) {
            qm.forceCompleteQuest();
            qm.dispose();
        }
    }
}