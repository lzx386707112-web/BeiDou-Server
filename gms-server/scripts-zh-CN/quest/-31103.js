// -31103 (TMS 34433) - [活動] 星光之塔開幕活動
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("#e星光之塔#n，墮落城市的全新地標！
為了共同創造了新歷史的大家，準備了特別的禮物。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("墮落廣場的新地標，完成星光之塔獲得禮物。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
