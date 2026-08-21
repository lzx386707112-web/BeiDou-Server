function start(ms) {
    ms.showEffect("customSkill/karing/perilsGoongiVideoLayer");
    var map = ms.getMap(410007140);
    ms.scheduleKaringBossOnGroundBelowIfMissing(map, 8880830, 568, 106, 2000, 410007160);
}
