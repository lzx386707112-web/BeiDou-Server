var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0 || selection == 1) {
            qm.sendOk("嗯……如果你改变主意了，随时可以再来找我。");
            qm.dispose();
            return;
        }
        if (mode == 1) status++; else status--;
        if (status == 0) {
            qm.sendNext("冒险岛联盟决定尽全力救出世界树。");
        } else if (status == 1) {
            qm.sendNextPrev("#b#h0#：#k\r\n既然有冒险岛联盟出面，我就放心了。");
        } else if (status == 2) {
            qm.sendNextPrev("世界树的生命力量，是足以和黑魔法师对抗的强大力量。\r\n过去要是没有世界树的帮助，我们也不可能把黑魔法师封印起来。\r\n但是因为那场战斗，世界树迅速地枯萎了。赫丽娜戴着世界树剩下的#b生命的根源#k，来到了金银岛。");
        } else if (status == 3) {
            qm.sendNextPrev("但是有一天生命的根源突然消失了，我们还担心会不会是被黑魔法师一伙抢走了，没想到她是在那种地方恢复力量……");
        } else if (status == 4) {
            qm.sendNextPrev("#b#h0#：#k\r\n我们必须保护世界树。虽然不知道将世界树封印起来的人是谁，但他们一定是不怀好意。\r\n要是世界树的力量落入他们的手中，不知道会发生什么事。");
        } else if (status == 5) {
            qm.sendNextPrev("#b#h0#：#k\r\n不过守护世界树的封印的人好像都不是等闲之辈。");
        } else if (status == 6) {
            qm.sendAcceptDecline("如果像你所说，他们都拥有强大的力量的话，一定会是非常艰苦的战斗。\r\n你能在这次的任务中助我们一臂之力吗？现在我们迫切需要人手。");
        } else if (status == 7) {
            qm.sendNext("#b#h0#：#k\r\n义不容辞！");
        } else if (status == 8) {
            qm.sendNext("我向你的勇气表示敬意。\r\n请你先去消灭封印守护者，解开世界树的封印。然后请你把世界树安全地带到圣地。");
        } else if (status == 9) {
            qm.sendNextPrev("冒险岛联盟已经公告了营救世界树的行动，动作快的人也许已经到达鲁塔比斯了。请你和他们一起，救出世界树。");
        } else if (status == 10) {
            qm.sendOk("以后，你可以通过#b导游妮妮#k，移动到鲁塔比斯。");
            qm.forceStartQuest();
            qm.forceStartQuest(30029, "start");
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
            qm.sendNext("虽然幸运地平安救出了世界树，可是所有的危险并没有消失。之前封印世界树的势力好像晚一步得知了世界树被运往圣地的事。他们#r复活了封印守护者#k，意图获得强大的黑暗力量吞噬金银岛。");
        } else if (status == 1) {
            qm.sendOk("为了阻止他们的阴谋，我们需要你持续不断的支援。希望你今后也为了冒险岛世界的和平而努力。");
            qm.forceCompleteQuest();
            qm.dispose();
        }
    }
}