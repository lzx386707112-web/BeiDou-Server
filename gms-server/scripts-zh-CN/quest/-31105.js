// -31105 (TMS 34431) - [星光之塔] 蒂雅的頭號粉絲
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("成功招募蒂雅。
需要透過與蒂雅的對話努力了解她。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("成為蒂雅的頭號粉絲。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
