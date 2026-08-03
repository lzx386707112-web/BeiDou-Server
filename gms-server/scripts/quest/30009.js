var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0 || selection == 1) {
            qm.sendOk("嗯……那你准备好之后再来找我吧。");
            qm.dispose();
            return;
        }
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("回来啦。在你离开的这段时间，来了很多人！");
        } else if (status == 1) {
            qm.sendNext("#b#h0#：#k\r\n都是来帮助我解开封印的人。冒险岛联盟答应把你从这里救出去，现在可以不用担心了。");
        } else if (status == 2) {
            qm.sendNext("#b#h0#：#k\r\n但是要想解开你的封印，必须消灭掉门外的封印守护者。你知道些什么吗？");
        } else if (status == 3) {
            qm.sendNext("我没办法离开这里，所以什么都不知道。但是我可以感受到黑暗的力量。");
        } else if (status == 4) {
            qm.sendAcceptDecline("画着#r时钟#k的门外流出来的黑暗力量最弱。你先去消灭画着#r时钟#k的门外的封印守护者吧。");
        } else if (status == 5) {
            qm.sendOk("一个人可能会很困难。虽然说是最弱，但我还是感觉浑身直起鸡皮疙瘩。所以你一定要和#r志同道合的同伴#k一起去！");
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest();
    qm.dispose();
}