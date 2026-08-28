// -31210 (TMS 34326) - [拉契爾恩]墜落
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("帶著負傷的防毒面具回到祕密據點了。 必須和老頭說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("蝦子面具在時間塔第1層。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
