// [反轉城市]順著河水流下來的物品 (TMS 37601)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("#r無名村莊#k的#b雷卡托#k好像有話想說，似乎是有關順著河水流下來的物品的事。\r\n\r\n#b接受任務？#k");
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
        qm.sendYesNo("已前往#r無名村莊#k確認了順著河水流下來的無線電。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("已前往#r無名村莊#k確認了順著河水流下來的無線電。");
        qm.dispose();
    }
}
