// -27075 (TMS 38461) - [每日任務] 拉契爾恩地區淨化作業
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("為了打造寧靜的夜晚，去擊敗500隻拉契爾恩的怪物吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("為了打造寧靜的夜晚，去擊敗500隻拉契爾恩的怪物吧。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
