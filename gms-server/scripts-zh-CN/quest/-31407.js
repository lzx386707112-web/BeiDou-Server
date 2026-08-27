// 任務 -31407 (TMS 34129) - [每日任務] 調查消逝的旅途
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("所有事物皆風化的空間－消逝的旅途。答應幫助時間神官，破解這個空間的謎題。完成每日提供的任務後，幫助時間神官的研究吧。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("任務已接受！完成後回來找我吧。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("所有事物皆風化的空間－消逝的旅途。答應幫助時間神官，破解這個空間的謎題。完成每日提供的任務後，幫助時間神官的研究吧。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("辛苦了！謝謝你的幫忙。");
        qm.dispose();
    }
}
