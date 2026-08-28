// -31209 (TMS 34327) - [拉契爾恩]惡夢時間塔1樓
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("和蝦子面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("蝦子面具幫忙開路了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
