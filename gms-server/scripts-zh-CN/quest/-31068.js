// -31068 (TMS 34468) - [阿爾卡娜]恢復樹藤豎琴2
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("光靠#t4036099:#似乎有些不夠，需要其他更強烈的聲音。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("已使用#t4036100:#改變樹木生長的方向，很快地藤條豎琴也會重回原本的樣貌吧！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
