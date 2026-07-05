function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "Crimson Queen is already present.");
        return;
    }
    rm.spawnMonster(8920000, 1, 60, 134);
    rm.mapMessage(5, "Crimson Queen has appeared.");
}
