// -31206 (TMS 34330) - [拉契爾恩]惡夢時間塔4樓
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("和老頭說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("老頭幫忙開路了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
