function enter(pi) {
    var eim = pi.getEventInstance();
    pi.playPortalSound();
    if (eim != null) {
        eim.exitPlayer(pi.getPlayer());
        return true;
    }
    pi.warp(105300303, "sp");
    return true;
}
