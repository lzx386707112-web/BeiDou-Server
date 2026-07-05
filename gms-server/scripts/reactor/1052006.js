function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "Pierre is already present.");
        return;
    }
    rm.spawnMonster(8900000, 1, 489, 454);
    rm.mapMessage(5, "Pierre has appeared.");
}
