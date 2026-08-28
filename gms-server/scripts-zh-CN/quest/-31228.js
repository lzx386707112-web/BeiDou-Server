// -31228 (TMS 34308) - [拉契爾恩]誰是'甦醒者'呢？2
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須跟居民們講話，確認誰是「甦醒者」。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("蝦面具是「甦醒者」。 因為淨化者突然出現，我們就逃回祕密據點了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
