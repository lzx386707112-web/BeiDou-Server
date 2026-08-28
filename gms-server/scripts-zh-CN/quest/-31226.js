// -31226 (TMS 34310) - [拉契爾恩]音樂盒的聲音？
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("要把音樂盒聲音的事跟老爺說。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("已跟著防毒面具抵達吵雜不夜城。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
