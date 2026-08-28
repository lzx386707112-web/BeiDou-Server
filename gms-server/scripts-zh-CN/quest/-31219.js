// -31219 (TMS 34317) - [拉契爾恩]露希妲尋找的惡夢
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("音樂盒是維持夢境的裝置。 摧毀音樂盒後，當居民們醒來時，夢境就崩塌了。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("露希妲正在到處尋找惡夢。 是什麼惡夢？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
