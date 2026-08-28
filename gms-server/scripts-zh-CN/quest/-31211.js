// -31211 (TMS 34325) - [拉契爾恩]舞會面具
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須和舞會面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("舞會面具就是音樂盒。 和在夜市一樣，她變成音樂盒了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
