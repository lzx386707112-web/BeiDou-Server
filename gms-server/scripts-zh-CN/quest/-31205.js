// -31205 (TMS 34331) - [拉契爾恩]決戰
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須在時間塔的最上層見到露希妲。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("露希妲消失了。 她會去哪呢？ "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
