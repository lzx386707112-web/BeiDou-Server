// -31124 (TMS 34412) - [星光之塔] 暴走的佩里!?
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("…先把收集到的拿過去吧！得裝作沒看見，但還是不免想著透過筆記得知#b佩里#k有這樣的才能，她似乎也有成為明日之星的資質。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("毫無保留地展現自己的長才不就是明星基本該做的事情嗎？喚醒暴走的佩里，述說關於她的才能。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
