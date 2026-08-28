// -31113 (TMS 34423) - [星光之塔] 出道當天
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("終於到來的出道日，大發娛樂的新人團體究竟能不能成功呢？但不知怎麼的#b赫一#k的表情並不開心。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("根據赫一的說法，團員們狀況變得很奇怪，是在演奏過練習室的吉他之後發生的，去調查一下練習室的吉他吧。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
