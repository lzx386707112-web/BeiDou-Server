// -31135 (TMS 34401) - [星光之塔] 星光之塔地下
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("骯髒的辦公室內，有人昏倒在裡面。好像是#b#p1052203##k耶，先試著把他搖醒看看！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("墮落廣場之星，#p1052203#過去究竟是什麼樣子呢？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
