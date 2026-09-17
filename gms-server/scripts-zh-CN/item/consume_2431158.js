function start() {
    var player = im.getPlayer();
    if (player.startMonsterVac()) {
        im.gainItem(2431158, -1);
    }
    im.dispose();
}
