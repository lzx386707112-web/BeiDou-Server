// [反轉城市]衷心期盼 (TMS 37619)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#rM高塔頂層#k的#b黑洞產生器#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("請移動到傳送點破壞#o8641059#。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo(" 已破壞#o8641059#。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk(" 已破壞#o8641059#。");
    } else if (status == 2) {
        qm.warp(450014050, 0);
        qm.dispose();
    }
}
