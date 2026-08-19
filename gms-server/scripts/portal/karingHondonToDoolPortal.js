function enter(pi) {
    return warpKaringBoss(pi, 410007180, 8880831, 556, 405);
}

function warpKaringBoss(pi, mapId, bossId, x, y) {
    var map = pi.getMap(mapId);
    if (map == null) {
        pi.playerMessage(5, "Karing map " + mapId + " is not loaded.");
        return false;
    }
    pi.playPortalSound();
    pi.warp(mapId, 0);
    return true;
}

function spawnKaringBoss(map, bossId, x, y) {
    if (map.getMonsterById(bossId) != null) {
        return;
    }
    var LifeFactory = Java.type("org.gms.server.life.LifeFactory");
    var Point = Java.type("java.awt.Point");
    var boss = LifeFactory.getMonster(bossId);
    if (boss != null) {
        map.spawnMonsterOnGroundBelow(boss, new Point(x, y));
    }
}
