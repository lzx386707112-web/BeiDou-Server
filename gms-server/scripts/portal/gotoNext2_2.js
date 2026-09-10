function enter(pi) {
    var items = [4032833];
    var quests = [3166, 3191];
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
        pi.playerMessage(5, "需要持有第二座塔的钥匙才能进入。");
        return false;
    }
    pi.playPortalSound();
    pi.warp(211060410, "in00");
    return true;
}
