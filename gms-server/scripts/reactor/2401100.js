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
    rm.mapMessage(6, "From the depths of his cave, here comes Chaos Horntail!");
}
