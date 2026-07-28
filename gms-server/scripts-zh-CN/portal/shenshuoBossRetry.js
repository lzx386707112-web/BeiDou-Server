var RETRY_CONFIG = {
    "262030300": [262030300, 8870000, 1092, 196, "bossRetry"],
    "262031300": [262031300, 8870200, 1092, 196, "bossRetry"],
    "450010100": [450010100, 8880400, 855, 266, "bossRetry"],
    "221040001": [221040001, 8880200, -1215, 866, "bossRetry"],
    "450009400": [450009400, 8645009, -1, -157, "bossRetry"],
    "900000207": [900000207, 8880700, 703, -1394, "bossRetry"],
    "410002060": [410002060, 8880803, 900, 325, "bossRetry"]
};

function enter(pi) {
    var config = RETRY_CONFIG[String(pi.getPlayer().getMapId())];
    if (config == null) {
        pi.getPlayer().dropMessage(5, "The retry portal is not configured for this map.");
        return false;
    }

    var targetMap = pi.getMap(config[0]);
    if (targetMap == null) {
        pi.getPlayer().dropMessage(5, "The boss map is not available.");
        return false;
    }

    // Preserve the current fight. Only create a new boss when the map no
    // longer contains one, such as after a completed or unloaded challenge.
    if (targetMap.getMonsterById(config[1]) == null) {
        const LifeFactory = Java.type('org.gms.server.life.LifeFactory');
        const Point = Java.type('java.awt.Point');
        var boss = LifeFactory.getMonster(config[1]);
        if (boss == null) {
            pi.getPlayer().dropMessage(5, "The boss resource is not available.");
            return false;
        }
        targetMap.spawnMonsterOnGroundBelow(boss, new Point(config[2], config[3]));
    }

    pi.playPortalSound();
    var portal = targetMap.getPortal(config[4]);
    if (portal == null) {
        portal = targetMap.getPortal(0);
    }
    pi.getPlayer().changeMap(targetMap, portal);
    return true;
}
