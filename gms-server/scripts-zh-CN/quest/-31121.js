// -31121 (TMS 34415) - [星光之塔] 亞咪的心意
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("幫她找回#i4036023:# #t4036023:#，她會不會多少有些動搖呢？再次向#b亞咪#k提出徵選提議吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("從#b#i4036023:# #t4036023:##k傳出的是赫一剛出道時的歌曲。亞咪是赫一的粉絲。這麼說，亞咪想去的地方是… "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
