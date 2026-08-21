function start(ms) {
    ms.showEffect("customSkill/karing/perilsDoolVideoLayer");
    var map = ms.getMap(410007180);
    ms.scheduleKaringBossOnGroundBelowIfMissing(map, 8880831, 568, 106, 2000, 410007200);
}
