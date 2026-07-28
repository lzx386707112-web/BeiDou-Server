function enter(pi) {
    var mapId = pi.getPlayer().getMapId();
    var targets = {
        105200100: 105200110,
        105200500: 105200110,
        105200600: 105200210,
        105200700: 105200310
    };
    if (mapId == 105200800) {
        pi.getPlayer().dropMessage(6, "该 Boss 路线暂未开放。");
        return false;
    }
    var target = targets[mapId] || (mapId + 10);
    pi.playPortalSound();
    pi.warp(target, "sp");
    return true;
}
