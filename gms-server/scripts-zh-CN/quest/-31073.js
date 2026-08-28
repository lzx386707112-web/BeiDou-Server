// -31073 (TMS 34463) - [阿爾卡娜]尋找消失的樹木精靈
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("得快點找到樹木的精靈，跟小精靈一起翻遍每個樹叢深處角落吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("找到獨自處在深幽樹林裡的樹木的精靈了！雖然他已被染上邪惡氣息，但還好似乎尚未完全失去意識。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
