function start(ms) {
    if (ms.isQuestStarted(31102)) {
        ms.setQuestProgress(31102, 31102, "end");
        ms.playerMessage(5, "任务已更新。");
    }
}
