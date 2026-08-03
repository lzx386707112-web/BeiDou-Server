function enter(pi) {
    if (pi.isQuestCompleted(30000) && !pi.isQuestCompleted(30007)) {
        pi.playPortalSound();
        pi.warp(910700200);
        return true;
    } else if (pi.isQuestCompleted(30007)) {
        pi.playPortalSound();
        pi.warp(105200000);
        return true;
    } else {
        pi.playerMessage(5, "一股神秘的力量把你拦在了外面");
        return false;
    }
}
