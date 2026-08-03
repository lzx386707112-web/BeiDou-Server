
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
            qm.sendNext("辛苦你了，我感到黑暗的力量减弱了一些。");
        } else if (status == 1) {
            qm.sendNext("#b#h0#：#k\r\n休整完毕，让我们继续吧！");
        } else if (status == 2) {
            qm.sendAcceptDecline("接下来就去消灭画着#r茶壶#k的门外的封印守护者吧。");
        }  else if (status == 3) {
            qm.sendOk("请别掉以轻心，还是和#r志同道合的同伴#k一起去吧！");
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest();
    qm.dispose();
}