// -31200 (TMS 34336) - [拉契爾恩] 毀夢者排行的禮物
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext(""); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("任務完成！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
