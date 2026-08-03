function enter(pi) {
    // 任务31180已完成：传送到 272030000
    if (pi.isQuestCompleted(31180)) {
        pi.playPortalSound();
        pi.warp(272030000);
        return true;
    }

    if (pi.getQuestStatus(31167) > 0 && !pi.isQuestCompleted(31178)) {
        pi.playPortalSound();
        pi.warp(272000100, 1);
    } else {
        pi.playPortalSound();
        pi.warp(272020000, 0);
    }
    return true;
}
