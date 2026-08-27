// 任務 -31389 (TMS 34147) - [每日任務]收集33個艾爾達斯的燈火樣本
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("收集33個#t4034930:#帶回來給蘿娜。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("任務已接受！完成後回來找我吧。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("把收集33個#t4034930:#帶回來給蘿娜了。\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("辛苦了！謝謝你的幫忙。");
        qm.dispose();
    }
}
