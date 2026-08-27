// [反轉城市]只不過是零件 (TMS 37615)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r地上列車1#k的#b倍爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("消滅#o8641055#取得#t4036635#。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        if (!qm.haveItem(4036635, 20)) {
            qm.sendOk("還需要#i4036635:# #t4036635:# 20個。");
            qm.dispose();
            return;
        }
        qm.sendYesNo("已把#t4036635#交給#b倍爾#k。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.gainItem(4036635, -20);
        qm.forceCompleteQuest();
        qm.sendOk("已把#t4036635#交給#b倍爾#k。");
        qm.dispose();
    }
}
