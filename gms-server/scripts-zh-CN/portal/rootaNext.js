function enter(pi) {
    var targets = {
        105200500: 105200510,
        105200600: 105200610,
        105200700: 105200710,
        105200800: 105200810
    };
    var target = targets[pi.getMapId()];
    if (target == null) {
        return false;
    }
    pi.playPortalSound();
    pi.warp(target, "sp");
    return true;
}
