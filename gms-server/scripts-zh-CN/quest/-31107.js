// -31107 (TMS 34429) - [星光之塔] 佩里的頭號粉絲
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("成功招募佩里。
需要透過與佩里的對話努力了解她。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("成為佩里的頭號粉絲。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
