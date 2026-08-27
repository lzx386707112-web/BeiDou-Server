// [反轉城市]我們不是老鼠 (TMS 37611)
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("和#r倍爾的居處#k的#b倍爾#k對話。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("前往#r地下線路避難處#k和#b倍爾#k對話。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("決定聯手對抗#bT-boy#k。\r\n必須跟著倍爾前往#r地下線路某處#k。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("決定聯手對抗#bT-boy#k。\r\n必須跟著倍爾前往#r地下線路某處#k。");
        qm.dispose();
    }
}
