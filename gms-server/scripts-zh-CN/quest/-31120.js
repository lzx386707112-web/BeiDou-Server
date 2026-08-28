// -31120 (TMS 34416) - [星光之塔] 發現巨星的原石 <4>
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("神祕的音色下，具有冷酷魅力的女孩！亞咪有成為巨星的可能性！對超酷美人#b亞咪#k遞出大發娛樂的名片吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("招募亞咪後回到辦公室。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
