function enter(pi) {
    if (pi.isQuestStarted(30002)) {
        pi.forceCompleteQuest(30002);
		pi.playerMessage(5, "任务完成");
        pi.playerMessage(5, "果然有出口。应该把这一事实告诉少女。");
        return false;
    } else if (pi.isQuestStarted(30003)) {
        pi.playPortalSound();
		pi.forceCompleteQuest(30003);
		pi.playerMessage(5, "任务完成");
        pi.playerMessage(5, "出口确实可以通向外面，难道只有那个少女没有办法离开那吗......");
        pi.warp(105040300);
        return true;
    }
    pi.playPortalSound();
    pi.warp(105040300);
    return true;
}