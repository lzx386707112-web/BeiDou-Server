function enter(pi) {
    if (pi.isQuestStarted(31124)) {
        pi.forceCompleteQuest(31124);
        pi.playerMessage(5, "任务完成。");
    }

    pi.playPortalSound();
    pi.warp(271030010, 0);
    return true;
}
