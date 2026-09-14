function enter(pi) {
    var em = pi.getEventManager("DamienBattle");
    if (em == null) {
        pi.playerMessage(5, "戴米安挑战尚未启用。");
        return false;
    }
    var eim = em.getInstance("DAMIEN" + pi.getPlayer().getClient().getChannel());
    if (eim != null && eim.getIntProperty("canJoin") == 1) {
        eim.registerPlayer(pi.getPlayer());
        return true;
    }
    pi.openNpc(1540895);
    return false;
}
