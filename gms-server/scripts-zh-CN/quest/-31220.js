// -31220 (TMS 34316) - [拉契爾恩]醒來的居民們
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("得跟老爺講個話。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("帶著防毒面具回到了祕密據點。 西瓜面具加入了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
