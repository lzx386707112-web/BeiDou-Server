function enter(pi) {
    var mapId = pi.getPlayer().getMapId();
    var targets = {
        105200100: 105200110,
        105200500: 105200110,
        105200600: 105200210,
        105200700: 105200310,
        105200800: 105200410
    };
    var target = targets[mapId] || (mapId + 10);
    pi.playPortalSound();
    pi.warp(target, "sp");
    return true;
}
