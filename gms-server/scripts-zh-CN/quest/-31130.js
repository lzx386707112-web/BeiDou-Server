// -31130 (TMS 34406) - [星光之塔] 需要喇叭線
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("#r露比#k似乎默默地想要演奏下一首歌曲，不過奇怪了耶？沒聲音，究竟是出了什麼問題。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("表演開始前露比的#b#i4036019:# #t4036019:##k卻突然斷掉，因此我幫他解決了困難。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
