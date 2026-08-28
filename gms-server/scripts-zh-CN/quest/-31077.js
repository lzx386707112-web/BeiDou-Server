// -31077 (TMS 34459) - [阿爾卡娜]花朵的私語
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("再次向出現的風精靈徵求意見吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("將說悄悄話的花群們所說的話中很在意的地方轉達給小精靈。似乎想起了什麼。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
