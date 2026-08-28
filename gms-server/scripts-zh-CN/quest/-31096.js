// -31096 (TMS 34440) - [星光之塔] 完美的出道準備
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("事前投票的結果，成為第一名'夢想舞台'的主人公的大發娛樂新人女團！現在就只差出道的完美準備了。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("為了幫助大發娛樂的新人女團出道，邀請了髮型師與化妝師。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
