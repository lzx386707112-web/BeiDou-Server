// -31212 (TMS 34324) - [拉契爾恩]再次前往舞會場
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("防毒面具沒有逃跑。 必須和留在#m450003440#的說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("抵達舞廳了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
