function enter(pi) {
    var returnMap = pi.getSavedLocation("EVENT");
    if (returnMap < 100000000 || returnMap == 910000000 || returnMap >= 105200000 && returnMap < 105300000) {
        returnMap = 105040300;
    }
    pi.playPortalSound();
    pi.warp(returnMap, "sp");
    return true;
}
