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
            qm.sendNext("你救了战神和我们种族，现在该去救双弩精灵了。你已经看到她倒下了吧？")
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n是的，看上去情况比战神还要糟糕。该怎么帮助她呢？")
        } else if (status == 2) {
            qm.sendNextPrev("双弩精灵承受了世界上所有精灵的诅咒，因此正在忍受更大的痛苦。如果她这样倒下的话，精灵们也会全部消失。为了阻止这样的事情发生，必须帮助双弩精灵重新站起来。为此，我能借助你的力量吗？")
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n没问题，我很乐意帮助你。")
        } else if (status == 4) {
            qm.sendNextPrev("请把你的力量借给我一些。你的体力可能会突然下降，别害怕。")
        } else if (status == 5) {
            qm.getPlayer().updateHp(33333);
            var curHp = qm.getPlayer().getHp();
            qm.getPlayer().updateHp(curHp / 2);
            qm.sendNextPrev("真让人吃惊。你体内的能力不输于刚才见到的所有英雄。我暂时恢复了大部分的能力。我会用这个力量，为你制造拯救双弩精灵的结晶。稍等一下。")
        } else if (status == 6) {
            qm.gainItem(4033082, 1);
            qm.sendOk("拿着我给你的阿弗利埃的精髓，去唤醒双弩精灵。只要轻轻碰一碰她，就行了。");
            qm.forceStartQuest();
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
