// -31115 (TMS 34421) - [星光之塔] 邀請化妝師
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("大發娛樂的新人女團為了要成功出道，決定尋找實力最強的化妝師。去#r5樓化妝品賣場#k找#b麗蔻塔#k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("收集#b#i4036024:# #t4036024:##k #b15個#k交給Ricotta，並且完成了交涉。現在剩下髮型師。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
