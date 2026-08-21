function start(ms) {
    ms.showEffect("customSkill/karing/perilsHondonVideoLayer");
    var map = ms.getMap(410007220);
    ms.scheduleKaringBossOnGroundBelowIfMissing(map, 8880832, 634, 106, 2000, 410007240);
}
