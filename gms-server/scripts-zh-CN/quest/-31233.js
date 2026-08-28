// -31233 (TMS 34303) - [拉契爾恩]害羞的防毒面具
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("防毒面具好像有什麼話想說。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("雖然已經收集到所有面具材料，但還沒做面具。 老爺的手滑了。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
