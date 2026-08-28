// -31067 (TMS 34469) - [阿爾卡娜]響徹的豎琴聲
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("正在著要找回藤條豎琴就看見樹木的精靈們出現在眼前。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("迷路的樹木的精靈代替其他夥伴表示歉意，但那所謂一股壞氣息的外地人究竟指的是誰呢？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
