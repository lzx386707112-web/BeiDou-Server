/*
    Chaos Horntail's Cave - Summons Chaos Horntail.
*/

function act() {
    rm.changeMusic("Bgm14/HonTale");
    var map = rm.getReactor().getMap();
    if (map.getMonsterById(8810130) == null && map.getMonsterById(8810118) == null && map.getMonsterById(8810119) == null && map.getMonsterById(8810120) == null && map.getMonsterById(8810121) == null && map.getMonsterById(8810122) == null) {
        map.spawnChaosHorntailOnGroundBelow(new java.awt.Point(71, 260));

        var eim = rm.getEventInstance();
        if (eim != null) {
            eim.restartEventTimer(60 * 60000);
        }
    }
    rm.mapMessage(6, "洞穴深处传来震天咆哮，进阶暗黑龙王破岩而出！");
}
