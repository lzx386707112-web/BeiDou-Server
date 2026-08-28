// -31126 (TMS 34410) - [星光之塔] 發現巨星的原石 <2>
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("可愛笑容下藏有爽朗性格的反差魅力！薩菲一定有成為明日之星的特質！將大發娛樂公司的名片交給打工生#r薩菲#k吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("結束薩菲的招募之後搭乘電梯前往3樓。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
