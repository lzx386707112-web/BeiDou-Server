// -31214 (TMS 34322) - [拉契爾恩]黑面具
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須跟黑色面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("防毒面具在保護黑色面具時受傷了。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
