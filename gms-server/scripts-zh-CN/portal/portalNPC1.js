function enter(pi) {
    var mapId = pi.getPlayer().getMapId();
    if (mapId == 272020110) {
        var eim = pi.getPlayer().getEventInstance();
        if (eim != null && eim.getName().startsWith("ArkariumBattle") && !eim.isEventCleared()) {
            var map = eim.getMapInstance(272020200);
            pi.getPlayer().changeMap(map, map.getPortal(0));
            return true;
        }

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
