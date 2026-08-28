// -31222 (TMS 34314) - [拉契爾恩]打破碟子吧1
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("河水流過來的方向。 即，要去左邊問音樂盒的位置。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("據說音樂盒的聲音是從派伊面具身上傳來的。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
