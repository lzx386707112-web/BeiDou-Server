// -31104 (TMS 34432) - 大發公司共同代表
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("作為幫助成功推出新人團體的獎勵，與赫一一起成為大發娛樂的共同代表。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("與赫一一起成為大發娛樂的共同代表。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
