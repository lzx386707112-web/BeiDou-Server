var BOSS_SPAWNS = {
    105200110: [8910100, 489, 454],
    105200210: [8900100, -131, 550],
    105200310: [8920100, 60, 134],
    105200410: [8930100, -192, 442],
    105200510: [8910000, 489, 454],
    105200610: [8900000, -131, 550],
    105200710: [8920000, 60, 134],
    105200810: [8930000, -192, 442]
};

function start(ms) {
    var spawn = BOSS_SPAWNS[ms.getMapId()];
    if (spawn == null || ms.countMonster() > 0) {
        return true;
    }
    var LifeFactory = Java.type("org.gms.server.life.LifeFactory");
    var Point = Java.type("java.awt.Point");
    ms.getPlayer().getMap().spawnMonsterOnGroundBelow(LifeFactory.getMonster(spawn[0]), new Point(spawn[1], spawn[2]));
    return true;
}
