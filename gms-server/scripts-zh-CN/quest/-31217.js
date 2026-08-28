// -31217 (TMS 34319) - [拉契爾恩]前往舞會場
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("音樂盒的位置在拉契爾恩舞會場那。 跟防毒面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("抵達拉契爾恩舞會場了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
