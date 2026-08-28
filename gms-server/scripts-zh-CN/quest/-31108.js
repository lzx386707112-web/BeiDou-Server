// -31108 (TMS 34428) - [星光之塔] 薩菲的頭號粉絲
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("成功招募薩菲。
需要透過與薩菲的對話努力了解她。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("成為薩菲的頭號粉絲。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
