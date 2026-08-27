// [反轉城市]在被破壞的都市存活 (TMS 37620)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r地下線路避難處#k的#b拉索爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("請依照任務指示前進。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("從#b拉索爾#k那裡聽到了#b倍爾#k的事情。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("從#b拉索爾#k那裡聽到了#b倍爾#k的事情。");
        qm.dispose();
    }
}
