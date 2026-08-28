// -31131 (TMS 34405) - [星光之塔] 聆聽美好音樂的回饋
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("在#r星光之塔大廳#k見到了街頭藝人#b露比#k，雖然技巧不夠純熟，但他充滿能量的嗓音，讓所有路人都為他喝采。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("對於音樂人來說觀眾的支持是最大的動力！雖然技巧不足，但率性的露比在午後的夕陽襯托下散發出耀眼光芒。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
