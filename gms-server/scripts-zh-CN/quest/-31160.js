// -31160 (TMS 34376) - 蝴蝶夢
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("六個在拉契爾恩主街出現的潛意識的裂痕都看到了。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("六個在拉契爾恩主街出現的潛意識的裂痕都看到了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
