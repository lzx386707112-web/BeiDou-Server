function enter(pi) {
    if (pi.isQuestStarted(31149)) {
        pi.forceCompleteQuest(31149);
        pi.playerMessage(5, "任务完成。");
    }

    pi.playPortalSound();
    pi.warp(271040000, 0);
    return true;
}
