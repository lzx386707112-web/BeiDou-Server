// -31074 (TMS 34462) - [阿爾卡娜]他們是樹木的精靈
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("雖到達了森林深處，但好像有什麼嚴重的誤解。和小精靈聊聊吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("依照風精靈所說的，其中一個樹精靈在森林深處某個地方。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
