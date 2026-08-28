// -31223 (TMS 34313) - [拉契爾恩]消失的伊莉莎白3
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("伊莉莎白沒有回來。 我要問一下是怎麼回事。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("伊莉莎白回來了。 音樂盒的位置是在河水流過來的方向，是左邊。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
