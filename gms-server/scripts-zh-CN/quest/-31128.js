// -31128 (TMS 34408) - [星光之塔] 幫我收集飲料材料
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("在#星光之塔2樓咖啡廳#k裡見到打工的#b薩菲#k，即使忙碌奔走著，臉上卻總是帶著笑容，讓周圍充滿明朗氛圍…但仔細看了一下，好像有什麼問題。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("幫助了因為#t4036020:#掉落感到慌張的薩菲。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
