// [反轉城市]最平凡的人 (TMS 37602)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r無名村莊#k的#b雷卡托#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("請前往#r反轉城市#k確認發生什麼事。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("前往#r反轉城市#k後，遇到了來歷不明的#bT-boy#k和#b拉索爾#k。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("前往#r反轉城市#k後，遇到了來歷不明的#bT-boy#k和#b拉索爾#k。");
        qm.dispose();
    }
}
