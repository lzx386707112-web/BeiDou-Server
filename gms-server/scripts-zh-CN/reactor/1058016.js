function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "半半已经出现。");
        return;
    }
    rm.spawnMonster(8910000, 1, -131, 550);
    rm.mapMessage(5, "半半出现了。");
}
