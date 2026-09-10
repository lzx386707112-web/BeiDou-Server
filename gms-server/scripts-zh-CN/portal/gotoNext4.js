function enter(pi) {
    var items = [4032840];
    var quests = [3193, 3194];
    var allowed = false;
    var i;
    for (i = 0; i < items.length; i++) {
        if (pi.haveItem(items[i], 1)) {
            allowed = true;
            break;
        }
    }
    if (!allowed) {
        for (i = 0; i < quests.length; i++) {
            if (pi.isQuestStarted(quests[i]) || pi.isQuestCompleted(quests[i])) {
                allowed = true;
                break;
            }
        }
    }
    if (!allowed) {
        pi.playerMessage(5, "需要持有第四座塔的钥匙才能进入。");
        return false;
    }
    pi.playPortalSound();
    pi.warp(211060800, "west00");
    return true;
}
