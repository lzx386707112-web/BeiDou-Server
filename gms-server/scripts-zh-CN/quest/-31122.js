// -31122 (TMS 34414) - [星光之塔] 請幫我找錄音機
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("#r星光之塔4樓天空花園#k。見到了擁有神祕音色的#b亞咪#k，雖然提出招募的提議，但她好像已經有想要去的地方…還沒有決定前，還有希望的，她應該往同一層的唱片行的方向過去了。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("找出混在 #b#i2436127:# #t2436127:##k 內的 #b#i4036023:# #t4036023:##k。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
