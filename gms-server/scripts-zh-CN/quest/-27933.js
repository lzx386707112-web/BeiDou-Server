// [反轉城市]在雨林中存活 (TMS 37603)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("#r地下線路避難處#k的#b阿拉莫#k好像有話要說。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("去拜託#r地下線路4#k的#b拉索爾#k帶路。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("從#b拉索爾#k那裡聽說了有關#b倍爾#k的情報。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("從#b拉索爾#k那裡聽說了有關#b倍爾#k的情報。");
        qm.dispose();
    }
}
