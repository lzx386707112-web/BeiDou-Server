function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "Vellum is already present.");
        return;
    }
    rm.spawnMonster(8930000, 1, -192, 442);
    rm.mapMessage(5, "Vellum has appeared.");
}
