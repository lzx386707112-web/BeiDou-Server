// -31134 (TMS 34402) - [星光之塔] 墮落廣場的超級巨星
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("看起來是對#p1052203#狂熱飯的少女，是#b#p1052205##k，向她詢問看看#p1052203#的狀況吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("幫忙取得的#b#i4036027:# #t4036027:##k #b25個#k當中有簽名會入場券。#p1052205#說那是只會提供感謝對象的高級情報，接著便告知#p1052203#的鞋子尺寸。連鞋子尺寸都很熱門，#p1052203#是當時的超級巨星。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
