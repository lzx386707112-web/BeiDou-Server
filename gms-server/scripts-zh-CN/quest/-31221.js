// -31221 (TMS 34315) - [拉契爾恩]打破碟子吧2
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("從派伊面具身上傳來了音樂盒的聲音。 要跟他講話才行。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("派伊面具變成音樂盒了。 雖然一把它摧毀，淨化者就消失了，但防毒面具很痛苦。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
