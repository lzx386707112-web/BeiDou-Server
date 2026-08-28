// -31116 (TMS 34420) - [星光之塔] 爭取出道節目
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("峰迴路轉之後，終於成立的大發娛樂的全新女團！現在只差出道了，蒂雅既然已經成為歌手，無法再兼任祕書的工作，準備作業該由誰來進行呢？與#b赫一#k討論看看。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("事前簡訊投票結果，大發娛樂的新人女團獲得壓倒性的第一名，成為'夢想舞台'的主角！大發娛樂的未來要開始大發了嗎？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
