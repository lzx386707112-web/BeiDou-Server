function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "血腥女王已经出现。");
        return;
    }
    rm.spawnMonster(8920000, 1, 60, 134);
    rm.mapMessage(5, "血腥女王出现了。");
}
