
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
            qm.sendAcceptDecline("接下来就是画着#r王冠#k的那个门了。");
        } else if (status == 1) {
            qm.sendNext("#b#h0#：#k\r\n一鼓作气解决他吧！");
        } else if (status == 2) {
            qm.sendOk("交给你们了！");
            qm.forceStartQuest();
            qm.dispose();
        }
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest();
    qm.dispose();
}