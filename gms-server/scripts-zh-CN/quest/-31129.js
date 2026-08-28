// -31129 (TMS 34407) - [星光之塔] 發現巨星的原石 <1>
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("雖然說技巧不夠純熟，但有一種吸引目光的魅力！露比一定有成為明星的資質！快將大發娛樂公司的名片遞交給#r露比#k吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("露比完成徵選面試之後搭乘電梯前往2樓。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
