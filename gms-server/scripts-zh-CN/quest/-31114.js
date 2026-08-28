// -31114 (TMS 34422) - [星光之塔] 邀請髮型師
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("為了大發娛樂新人組合的成功出道，決定要邀請眼光最好的髮型師。前往#r6樓髮廊#k去找#b帕尼爾#k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("收集#b#i4036025:# #t4036025:##k #b15個#k交給帕尼羅，完成了交涉。現在回去赫一的辦公室吧。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
