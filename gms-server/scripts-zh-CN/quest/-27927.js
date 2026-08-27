// [反轉城市]保安失敗 (TMS 37609)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#rT-boy的研究列車1#k的#b拉索爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("前往#rT-boy的研究列車3#k和#b拉索爾#k對話。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("已前往#rT-boy的研究列車3#k。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("已前往#rT-boy的研究列車3#k。");
        qm.dispose();
    }
}
