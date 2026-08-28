// -31225 (TMS 34311) - [拉契爾恩]消失的伊莉莎白1
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須跟居民們講話，詢問音樂盒的位置。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("原來伊莉莎白是雞。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
