function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "Von Bon is already present.");
        return;
    }
    rm.spawnMonster(8910000, 1, -131, 550);
    rm.mapMessage(5, "Von Bon has appeared.");
}
