// -31083 (TMS 34453) - [阿爾卡娜]森林之歌
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("森林樂曲的消失如果是破壞和諧的原因的話……，要不要詳細問一下有關森林樂曲的事情？"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("在聊著讓天然物發出聲音的方法時，出現不知在哪偷聽的風精靈。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
