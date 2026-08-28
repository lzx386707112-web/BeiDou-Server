// -31097 (TMS 34439) - [星光之塔] 經紀人出動！
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("出發前，先聽一下祕書#b#p1052212##k說明有關招募的基本吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("在星光之塔大廳遇到街道的解說員露比。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
