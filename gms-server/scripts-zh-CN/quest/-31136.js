// -31136 (TMS 34400) - [星光之塔] 開啟星光之塔
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("來自墮落地鐵的#p1052006#信件，究竟有什麼事情呢？"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("#p1052006#身為老朋友，對於過去新星#p1052203#的挫折感到非常惋惜，甚至從好幾天前就開始足不出戶…由於#p1052006#太過忙碌，代替他去找#r#m103041001##k吧！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
