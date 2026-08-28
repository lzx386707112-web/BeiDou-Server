// -31111 (TMS 34425) - [星光之塔] 華麗出道之後
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("華麗出道後，就如同大發娛樂的名稱一樣，聲名大噪。出道同時登上音樂節目第一名，出道歌曲不斷刷新紀錄，讓地下１０樓的赫一的辦公室一口氣升到#r星光之塔空中樓層#k。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("聽到了代表所有團員的蒂亞傳達的感謝。就這樣，#r星光之塔#k赫一的新人女團成功神話傳遍大小街巷。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
