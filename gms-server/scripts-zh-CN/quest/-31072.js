// -31072 (TMS 34464) - [阿爾卡娜]再一次
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("為了淨化迷路的樹木的精靈必須讓它重回夥伴們的懷抱，擊退周圍邪惡的精靈前望叢林深處吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("迷路的樹木的精靈已重回夥伴們的懷抱。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
