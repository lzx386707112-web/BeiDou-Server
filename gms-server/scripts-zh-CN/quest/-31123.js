// -31123 (TMS 34413) - [星光之塔] 發現巨星的原石 <3>
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("持之以恆的努力、歷經歲月的淬鍊、創造出絕佳的的情感表現！#b佩里#k一定有成為明星的資質！別讓她成為一個才華被埋沒的少女，快把大發娛樂公司名片交給佩里吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("完成佩里徵選後搭乘電梯前往4樓天空花園。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
