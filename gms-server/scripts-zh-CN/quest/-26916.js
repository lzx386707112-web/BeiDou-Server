// -26916 (TMS 38620) - [6轉] 拉契爾恩符文回收
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須越過靈魂艾爾達的激流，找回符文。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("找回了拉契爾恩的符文。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
