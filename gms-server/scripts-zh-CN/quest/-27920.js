// [反轉城市]那傢伙在那裡。 (TMS 37616)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r地上列車1#k的#b倍爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("前往#r地上列車3#k和#b倍爾#k對話。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("已前往#r地上列車3#k和#b倍爾#k對話。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("已前往#r地上列車3#k和#b倍爾#k對話。");
        qm.dispose();
    }
}
