function enter(pi) {
    var player = pi.getPlayer();
    pi.playPortalSound();

    if (player.canRecoverLastBanish()) {
        var banishInfo = player.getLastBanishData();
        player.changeMap(banishInfo.getLeft(), banishInfo.getRight());
        player.clearBanishPlayerData();
        return true;
    }

    if (pi.getEventInstance() != null) {
        pi.warp(271040100, 0);
        return true;
    }

    pi.warp(271040200, 0);
    return true;
}
