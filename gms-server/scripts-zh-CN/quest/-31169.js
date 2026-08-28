// -31169 (TMS 34367) - [夢之都拉契爾恩] 惡夢的主人擊敗者
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("需要擊敗惡夢的主人。#b\r\n\r\n請擊敗露希妲(困難)。\r\n"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("擊敗惡夢的主人，獲得&lt;惡夢的主人擊敗者&gt;稱號。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
