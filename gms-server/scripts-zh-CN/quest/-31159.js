// -31159 (TMS 34377) - [每日任務] 大爺的請託
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("聽說在拉契爾恩據點的大爺需要幫忙。\r\n快到 #r據點#k找找#b大爺#k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("到達了拉契爾恩並和#b大爺#k對話。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
