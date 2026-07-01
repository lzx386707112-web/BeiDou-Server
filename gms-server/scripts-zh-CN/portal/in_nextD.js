function enter(pi) {
    if (pi.isQuestStarted(31144)) {
        pi.forceCompleteQuest(31144);
        pi.playerMessage(5, "任务完成。");
    }

    pi.playPortalSound();
    pi.warp(271020000, 0);
    return true;
}
