// -31075 (TMS 34461) - [阿爾卡娜]前往森林深處
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("已將草笛放回原位，這就來找下一個天然物吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("雖到達了森林深處，但好像有什麼嚴重的誤解。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
