// -31142 (TMS 34394) - [每日任務] 回收50個睡眠粉
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("收集可以從所有拉契爾恩怪物身上獲得的
#i4036572:#  #t4036572:# #r50個#k後，交給#b#m450003100:##k的#b#p3003209:##k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("#b#p3003209:##k請求的#i4036572:##t4036572:##r50個#k已收集完成。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
