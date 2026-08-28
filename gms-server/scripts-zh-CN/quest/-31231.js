// -31231 (TMS 34305) - [拉契爾恩]會合
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("帶著老爺幫你做的面具跟防毒面具講話吧。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("遵照防毒面具的勸誘，決定跟'甦醒者'一起行動。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
