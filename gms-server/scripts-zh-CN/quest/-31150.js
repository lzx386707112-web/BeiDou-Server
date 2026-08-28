// -31150 (TMS 34386) - [每日任務] 消滅200個鬧脾氣的優勝碟
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("擊退#b#o8643006:##k#r200隻#k之後去找#b#m450003100:##k的#b#p3003209:##k吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("#b#p3003209:##k請求的#b#o8643006:##k #r200隻#k已完成擊殺。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
