function enter(pi) {
	if (pi.isQuestStarted(31144)) {
        pi.forceCompleteQuest(31144);
		pi.playerMessage(5, "任务完成。");
        pi.giveCharacterExp(50000, pi.getPlayer());
    }
    pi.playPortalSound();
    pi.warp(271010500, 0);
    return true;
}
