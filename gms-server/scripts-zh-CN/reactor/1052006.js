function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "皮埃尔已经出现。");
        return;
    }
    rm.spawnMonster(8900000, 1, 489, 454);
    rm.mapMessage(5, "皮埃尔出现了。");
}
