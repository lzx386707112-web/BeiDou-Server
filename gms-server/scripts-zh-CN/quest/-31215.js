// -31215 (TMS 34321) - [拉契爾恩]瘋狂的舞會場居民
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("獲得華麗的面具了。 現在從居民那取得情報看看。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("教訓狂放的舞會居民了，我要到黑假面身邊。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
