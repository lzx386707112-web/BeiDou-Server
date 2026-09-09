function enter(pi) {
    if (pi.getPlayer().getMap().countMonsters() > 0) {
        pi.playerMessage(5, "必须先消灭这张地图上的所有怪物，才能离开。");
        return false;
    }
    if (pi.canHold(4310020, 50)) {
        pi.gainItem(4310020, 50);
        pi.playerMessage(5, "获得了 50 枚怪物公园纪念币。");
    } else {
        pi.playerMessage(5, "其他栏已满，未能领取怪物公园纪念币。");
    }
    pi.playPortalSE();
    pi.warp(951000400, "sp");
    return true;
}
