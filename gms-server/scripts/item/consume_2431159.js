function start() {
    var player = im.getPlayer();
    if (player.getParty() == null) {
        player.dropMessage(5, "请先开启组队后再使用基友集合。未消耗道具。");
        im.dispose();
        return;
    }
    if (player.startPartyGrindCompanions()) {
        im.gainItem(2431159, -1);
    }
    im.dispose();
}
