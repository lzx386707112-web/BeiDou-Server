// -31216 (TMS 34320) - [拉契爾恩]服儀要求
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("跟居民說話。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("獲得華麗的面具了。 現在可以和其他居民說話了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
