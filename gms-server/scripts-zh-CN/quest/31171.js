var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("我想了一下，如果能把主人带到里恩岛上，在那里由纯争寒气构成的冰川中封印起来，也许可以阻止诅咒。至少可以让诅咒不再进一步恶化。");
        } else if (status == 1) {
            qm.sendNextPrev("问题是现在我的力量变得很弱，没办法移动到那里去。如果不是为了保护主人，和这里剩下的怪物战斗的话……那时为了保护主人，我只能把自己的力量全部释放出来。");
        } else if (status == 2) {
            qm.sendOk("在附近的怪物身上，应该可以找到含有我的力量的矛碎片。你去消灭怪物，帮我搜集#b50个碎裂的矛碎片#k。那样的话，我就应该可以获得将主人带到里恩岛上去的力量。");
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
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("碎裂的矛碎片全部搜集到了吗？");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n给，这样就够了吗？");
        } else if (status == 2) {
            qm.sendNextPrev("嗯，用这些来恢复力量的话……");
        } else if (status == 3) {
            qm.sendNextPrev("呼，虽然没有全部恢复，但总算恢复了一些力量。现在我要带着主人到里恩岛去了。\r\n有时间的话，我想见见阿弗利埃……你去帮我向他问好。");
        } else if (status == 4) {
            qm.sendNextPrev("#b#h0#：#k\r\n阿弗利埃是谁？");
            qm.forceCompleteQuest();
        } else if (status == 5) {
            qm.sendNextPrev("他是玛瑙龙之王。通过右边的传送口，应该就能见到他。他的体型很大，别被吓着了。熟悉了之后你就会发现，他其实是个很慈祥的人。\r\n多亏了你，主人终于得救了。");
        } else if (status == 6) {
            qm.sendOk("别忘了代我向阿弗利埃问好。");
            qm.forceStartQuest(31183);
            qm.dispose();
        }
    }
}