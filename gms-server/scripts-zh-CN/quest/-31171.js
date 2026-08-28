// -31171 (TMS 34365) - 惡夢之主擊殺者
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("惡夢的主人擊敗者"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("惡夢的主人擊敗者"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
