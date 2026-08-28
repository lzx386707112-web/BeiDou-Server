// -31207 (TMS 34329) - [拉契爾恩]惡夢時間塔3樓
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("和黑色面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("黑色面具幫忙開路了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
