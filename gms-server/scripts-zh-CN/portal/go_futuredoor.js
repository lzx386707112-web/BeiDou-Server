function enter(pi) {
    if (!pi.isQuestCompleted(31101)) {
        pi.getPlayer().message("你还不能从这里进去！");
        return false;
    }
	else if (pi.isQuestStarted(31102)) {
        pi.forceCompleteQuest(31102);
		pi.playerMessage(5, "任务完成。");
        pi.giveCharacterExp(50000, pi.getPlayer());
    }
    pi.playPortalSound();
    pi.warp(271000000, 3);
    return true;
}
