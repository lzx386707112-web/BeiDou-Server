// -31218 (TMS 34318) - [拉契爾恩]第二個音樂盒
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須跟在祕密據點的西瓜面具問問音樂盒聲音的事。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("第二個音樂盒，位於拉契爾恩舞會場。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
