// -31163 (TMS 34373) - [夢境碎片]第四層潛意識
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("還有某處令人在意的裂痕。 裂痕的另一頭好像和潛意識空間連在一起…"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("收集#i4034986:# #b#t4034986:##k，將潛意識的裂痕恢復原狀，進入潛意識空間了。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
