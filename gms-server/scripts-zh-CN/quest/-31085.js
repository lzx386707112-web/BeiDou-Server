// -31085 (TMS 34451) - [阿爾卡娜]小精靈
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("從具威脅性的精靈那裡救出了一隻小精靈，靠近他與他對話吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("根據小精靈所說的，並不是一開始附近就有光之漩渦。這裡肯定是發生了什麼事情。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
