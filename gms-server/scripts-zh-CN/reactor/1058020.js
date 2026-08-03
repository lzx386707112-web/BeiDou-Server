function act() {
    if (rm.countMonster() > 0) {
        rm.mapMessage(5, "贝伦已经出现。");
        return;
    }
    rm.spawnMonster(8930000, 1, -192, 442);
    rm.mapMessage(5, "贝伦出现了。");
}
