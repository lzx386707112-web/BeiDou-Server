// -31234 (TMS 34302) - [拉契爾恩]無法脫離的慶典都市
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("我還有事要問老爺。 我要跟他說話。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("無法擺脫紅霧，幸好「甦醒者」的祕密據點看起來很安全。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
