// [反轉城市]你的家鄉在哪？ (TMS 37606)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r地下線路6#k的#b拉索爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("獵捕#o8641052#取得倍爾喜歡的#t4036632#。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        if (!qm.haveItem(4036632, 20)) {
            qm.sendOk("還需要#i4036632:# #t4036632:# 20個。");
            qm.dispose();
            return;
        }
        qm.sendYesNo("把#t4036632#交給#b拉索爾#k後見到了倍爾。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.gainItem(4036632, -20);
        qm.forceCompleteQuest();
        qm.sendOk("把#t4036632#交給#b拉索爾#k後見到了倍爾。");
        qm.dispose();
    }
}
