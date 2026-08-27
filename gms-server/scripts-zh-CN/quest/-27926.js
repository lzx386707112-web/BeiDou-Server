// [反轉城市]那是什麼？ (TMS 37610)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#rT-boy的研究列車3#k的#b拉索爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("消滅#o8641054#取得#t4036633#。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        if (!qm.haveItem(4036633, 20)) {
            qm.sendOk("還需要#i4036633:# #t4036633:# 20個。");
            qm.dispose();
            return;
        }
        qm.sendYesNo("已取得#t4036633#。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.gainItem(4036633, -20);
        qm.forceCompleteQuest();
        qm.sendOk("已取得#t4036633#。");
        qm.dispose();
    }
}
