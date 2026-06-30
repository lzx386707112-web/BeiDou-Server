/*
    Chaos Zakum Altar - summons Chaos Zakum.
*/

function act() {
    if (rm.getPlayer().getEventInstance() != null) {
        rm.getPlayer().getEventInstance().setProperty("summoned", "true");
        rm.getPlayer().getEventInstance().setProperty("canJoin", "0");
    }

    rm.changeMusic("Bgm06/FinalFight");
    rm.spawnFakeMonster(8800100);
    for (var mobId = 8800103; mobId <= 8800110; mobId++) {
        rm.spawnMonster(mobId);
    }
    rm.createMapMonitor(280030001, "sp");
    rm.mapMessage(5, "Chaos Zakum has been summoned by the force of Eye of Fire.");
}
