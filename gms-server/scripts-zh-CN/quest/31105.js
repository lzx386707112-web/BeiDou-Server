var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.dispose();
            return;
        }

        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
           qm.sendNext("但是你到底是怎么来的呢？自从受到希纳斯的攻击之后，和其他地区的联系就中断了。");
		   // qm.askYesNo("要塞骑士团的动向不太寻常。\r\n好像在计划什么。我好像需要些帮助……");
        } else if (status == 1) {
            qm.sendNext("(不能说是从过去来的……)啊，我突然失去了知觉，醒来之后就到了这里，我也不记得怎么过来的了。你能给我说明一下现在的情况吗？");
        } else if (status == 2) {
            qm.sendOk("由于战争的冲击，暂时失去记忆了吗……希纳斯在黑魔法师的影响下变得堕落了。冒险骑士团变成了我们的敌人。他们攻击了我们，你也看到了，我们村……在那次袭击中，我父亲去世了……我不想再提起这悲伤的往事了。详细的情况，你去问赫丽娜吧。");
        }else if (status == 3) {
            qm.forceCompleteQuest();
			qm.gainExp(7000);
            qm.dispose();
        }
    }
}
function isAllSubquestsDone() {
    for (var i = 31105; i < 31106; i++) {
        if (!qm.isQuestCompleted(i)) {
            return false;
        }
    }

    return true;
}
