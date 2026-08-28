// -31110 (TMS 34426) - [星光之塔] 赫伊的朋友
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("曾經是巨星的赫一，成為他選拔人才的經紀人，幫他找回過去的榮耀吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("與赫一成為真誠的朋友。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
