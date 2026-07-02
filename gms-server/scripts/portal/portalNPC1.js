function enter(pi) {
    var mapId = pi.getPlayer().getMapId();
    if (mapId == 272020110) {
        var em = pi.getEventManager("ArkariumBattle");
        if (em == null || !em.startInstance(pi.getPlayer())) {
            pi.getPlayer().dropMessage(5, "祭坛的时空还没有稳定，请稍后再试。");
        }
        return true;
    }
    pi.playPortalSound();
    pi.warp(272020110, 0);
    return true;
}
