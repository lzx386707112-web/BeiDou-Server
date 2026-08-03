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
            qm.sendNext("……你是谁？")
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n(哇，真大啊。)我是#h0#。摩诃让我向你问好。")
        } else if (status == 2) {
            qm.sendNextPrev("摩诃……他怎么样了？和战神在一起吗？")
        } else if (status == 3) {
            qm.sendNextPrev("#b#h0#：#k\r\n他带着战神去了里恩岛。说要在那里把战神封印起来。")
        } else if (status == 4) {
            qm.sendNextPrev("原来如此。谢谢你救了我的朋友，未来的朋友。")
        } else if (status == 5) {
            qm.sendNextPrev("#b#h0#：#k\r\n……！！你是怎么知道的？")
        } else if (status == 6) {
            qm.sendNextPrev("我可是玛瑙龙之王。除了战神之外，你还可以帮助我们所有人。\r\n我和弗里德、战神和摩诃，还有双弩精灵等等，终于突破了艰难险阻，站在了黑魔法师面前。虽然谁也没见过黑魔法师的本体，但从他身上感觉到的强烈的邪恶气息，就能知道他就是黑魔法师。")
        } else if (status == 7) {
            qm.sendNextPrev("但是他的压倒性的魔力已经丧失了大半，因为曾经是黑魔法师左右手的恶魔猎手网刚和黑魔法师展开了殊死决战。恶魔猎手无法原谅杀死自己家人的黑魔法师。我们抓住这个机会，开始和黑魔法师战斗。")
        } else if (status == 8) {
            qm.sendNextPrev("即使是这样，黑魔法师仍然很强。身经百战的英雄们如果不是齐心协力的话，是绝对不可能把他打倒的。最后我们全都受了重伤，好不容易把他封印了起来。")
        } else if (status == 9) {
            qm.sendNextPrev("#b#h0#：#k\r\n听摩诃说，黑魔法师在被封印的瞬间施加了强力诅咒……")
        } else if (status == 10) {
            qm.sendNextPrev("没错。黑魔法师利用封印瞬间的那股力量，对包括我和弗里德在内的所有人施加了诅咒。这个诅咒非常强烈，所以我只能代替弗里德一个人承受了诅咒，因此慢慢地被冰冻了起来。")
        } else if (status == 11) {
            qm.sendNextPrev("#b#h0#：#k\r\n没有其他解开诅咒的方法吗？")
        } else if (status == 12) {
            qm.sendOk("如果解开黑魔法师的封印，诅咒应该就会解开。但是这样的事情绝不会发生。我和弗里德设计的封印，会把他永远束缚在那里。\r\n我没有力气说更多的话，你能过会儿再来和我说话吗？我得休息一下。");
            qm.forceStartQuest();
            qm.forceCompleteQuest();
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
            qm.sendNext("碎裂的矛碎片全部搜集到了吗？")
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n给，这样就够了吗？")
        } else if (status == 2) {
            qm.sendNextPrev("嗯，用这些来恢复力量的话……")
        } else if (status == 3) {
            qm.sendNextPrev("呼，虽然没有全部恢复，但总算恢复了一些力量。现在我要带着主人到里恩岛去了。有时间的话，我想见见阿弗利埃……你去帮我向他问好。")
        } else if (status == 4) {
            qm.sendNextPrev("阿弗利埃是谁？");
            qm.forceCompleteQuest()
        } else if (status == 5) {
            qm.sendNextPrev("他是玛瑙龙之王。通过右边的传送口，应该就能见到他。他的体型很大，别被吓着了。熟悉了之后你就会发现，他其实是个很慈祥的人。多亏了你，主人终于得救了。")
        } else if (status == 6) {
            qm.sendOk("别忘了代我向阿弗利埃问好。");
            qm.forceStartQuest(31183);
            qm.dispose()
        }
    }
}
