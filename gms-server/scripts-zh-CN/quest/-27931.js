// [反轉城市]紫色老鼠肉 (TMS 37605)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r地下線路4#k的#b拉索爾#k對話，移動到下一個地區。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("前往#r地下線路6#k和#b拉索爾#k對話。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("#b拉索爾#k說明了有關紫色老鼠肉的事。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("#b拉索爾#k說明了有關紫色老鼠肉的事。");
        qm.dispose();
    }
}
