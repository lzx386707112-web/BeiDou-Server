// -31232 (TMS 34304) - [拉契爾恩]無法專注
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("為了聽防毒面具的故事，就必須接受老爺的面具。 跟老爺聊聊吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("老爺完成面具了。 雖然看起來不怎麼樣，卻是跟你臉型吻合的好面具"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
