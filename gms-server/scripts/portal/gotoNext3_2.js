function enter(pi) {
    var items = [4032834];
    var quests = [3167, 3192];
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
        pi.playerMessage(5, "需要持有第三座塔的钥匙才能进入。");
        return false;
    }
    pi.playPortalSound();
    pi.warp(211060610, "in00");
    return true;
}
