/*
    Chaos Horntail's Cave - Summons Chaos Horntail.
*/

function act() {
    rm.changeMusic("Bgm14/HonTale");
    if (rm.getReactor().getMap().getMonsterById(8810026) == null && rm.getReactor().getMap().getMonsterById(8810018) == null) {
        rm.getReactor().getMap().spawnChaosHorntailOnGroundBelow(new java.awt.Point(71, 260));

        var eim = rm.getEventInstance();
        if (eim != null) {
            eim.restartEventTimer(60 * 60000);
        }
    }
    rm.mapMessage(6, "洞穴深处传来震天咆哮，进阶暗黑龙王破岩而出！");
}
