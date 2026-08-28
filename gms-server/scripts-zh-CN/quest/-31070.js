// -31070 (TMS 34466) - [阿爾卡娜]樹藤豎琴所在的地方
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("既然如此只好在沒有樹木的精靈的幫助下找出藤條豎琴的所在地。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("光環帶領著我們前往先前發現迷路樹木的精靈的所在位置。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
