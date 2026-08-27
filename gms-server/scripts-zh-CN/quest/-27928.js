// [反轉城市]找到方法了嗎？ (TMS 37608)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#rT-boy的研究列車1#k的#b拉索爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("消滅#o8641053#。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("已把包圍的#o8641053#全部消滅。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("已把包圍的#o8641053#全部消滅。");
        qm.dispose();
    }
}
