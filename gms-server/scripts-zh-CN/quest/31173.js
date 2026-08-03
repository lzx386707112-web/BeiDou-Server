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
            qm.sendNext("黑魔法师的诅咒对所有的玛瑙龙都产生了影响。存在于这片土地上的玛瑙龙正在逐渐死去。这样下去的话，我们就要灭绝了。")
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n怎么会发生这种事？")
        } else if (status == 2) {
            qm.sendNextPrev("我们是黑魔法师最大的对手。黑魔法师拼命想拉拢我们，但是我们拒绝了他的提议，站出来和黑魔法师对抗。之后他就一直把我们当成眼中钉，肉中刺。但是他的诅咒并不完美。因此我才能把他对我的朋友弗里德施加的诅咒转移到我的身上。")
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n为什么呢？")
        } else if (status == 4) {
            qm.sendNextPrev("失去种族的王还留在这个世界上干什么呢？与其这样，还不如让自己的朋友活下去。\r\n当然，我也有事情要他去做。")
        } else if (status == 5) {
            qm.sendNextPrev("#b#h0#：#k\r\n我能问问是什么事情吗？")
        } else if (status == 6) {
            qm.sendNextPrev("没关系。原来我们种族拥有近乎无限的生命，但后代却非常稀少。因为这次战争，原本为数不多的族人几乎全部死了，剩下的孩子们也受到了诅咒。但还好不久前出生了一个受到祝福的新生命。那个孩子还没从蛋中孵化，因此才能摆脱黑魔法师的诅咒。")
        } else if (status == 7) {
            qm.sendNextPrev("但是在和黑魔法师展开最后决战的时候，我把它掉在了神木村的什么地方。所以我想手托弗里德回到神木村去，把那个孩子转移到安全的地方。但是没想到弗里德在这漫长的时间里都没能醒来。")
        } else if (status == 8) {
            qm.sendNextPrev("所以我想拜托你。请你找到我们最后的孩子。")
        } else if (status == 9) {
            qm.sendOk("如果中途把最后的玛瑙龙蛋弄丢了的话，请放弃任务，重新和我对话。");
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
