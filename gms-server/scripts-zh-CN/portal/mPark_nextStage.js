function enter(pi) {
    if (pi.getPlayer().getMap().countMonsters() > 0) {
        pi.playerMessage(5, "必须先消灭这张地图上的所有怪物，才能进入下一阶段。");
        return false;
    }
    var next = pi.getMapId() + 100;
    var eim = pi.getPlayer().getEventInstance();
    var target = eim != null ? eim.getMapInstance(next) : pi.getWarpMap(next);
    if (target == null) {
        pi.playerMessage(5, "没有下一阶段。");
        return false;
    }
    pi.playPortalSound();
    pi.getPlayer().changeMap(target, target.getPortal(0));
    return true;
}
