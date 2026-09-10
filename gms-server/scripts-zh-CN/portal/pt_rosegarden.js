function enter(pi) {
    if (!(pi.haveItem(4032836, 1) || pi.isQuestStarted(3174) || pi.isQuestCompleted(3174))) {
        pi.playerMessage(5, "需要持有玫瑰庭园的钥匙才能进入。");
        return false;
    }
    pi.playPortalSound();
    pi.warp(211080000, "west00");
    return true;
}
