// -31202 (TMS 34334) - [拉契爾恩] 午夜的捉迷藏 2
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("#p9010100#似乎又有些話想說。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("現在好像不用陪夢中的破布娃娃玩也可以了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
