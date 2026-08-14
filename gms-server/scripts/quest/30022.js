var status = -1;
var QUEST_ID = 30022;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        qm.sendAcceptDecline("要领取今天的鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        qm.forceStartQuest(QUEST_ID);
        qm.forceCompleteQuest(QUEST_ID);
        qm.dispose();
    }
}

function end(mode, type, selection) {
    qm.forceCompleteQuest(QUEST_ID);
    qm.dispose();
}
