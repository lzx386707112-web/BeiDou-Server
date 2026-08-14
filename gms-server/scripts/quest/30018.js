var status = -1;
var QUEST_ID = 30018;
var ITEM_REQUIREMENTS = {
    30017: [4001755, 20],
    30020: [4001756, 20]
};
var INFO_PROGRESS = {
    30014: "clear",
    30015: "clear",
    30016: "clear",
    30018: "5",
    30019: "clear",
    30021: "clear"
};

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        qm.sendAcceptDecline("要开始执行鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        qm.forceStartQuest(QUEST_ID);
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
        return;
    }
    if (mode == 1) status++; else status--;
    if (status == 0) {
        var req = ITEM_REQUIREMENTS[QUEST_ID];
        if (req != null && !qm.haveItem(req[0], req[1])) {
            qm.sendOk("还需要 #b" + req[1] + " 个 #t" + req[0] + "##k。");
            qm.dispose();
            return;
        }
        qm.sendAcceptDecline("要完成这个鲁塔比斯每日任务吗？");
    } else if (status == 1) {
        var req = ITEM_REQUIREMENTS[QUEST_ID];
        if (req != null) {
            qm.gainItem(req[0], -req[1]);
        }
        var progress = INFO_PROGRESS[QUEST_ID];
        if (progress != null) {
            qm.setQuestProgress(QUEST_ID, QUEST_ID, progress);
        }
        qm.forceCompleteQuest(QUEST_ID);
        qm.dispose();
    }
}
