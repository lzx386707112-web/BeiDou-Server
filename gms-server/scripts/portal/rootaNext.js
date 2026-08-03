function enter(pi) {
    var mapId = pi.getPlayer().getMapId();

    if (pi.isQuestActive(30009)||pi.isQuestActive(30010)||pi.isQuestActive(30011)||pi.isQuestActive(30012)) {
        // 任务30009进行中且30012未完成：按现有逻辑传送
        var targets = {
            105200100: 105200110,
            105200500: 105200110,
            105200600: 105200210,
            105200700: 105200310,
            105200800: 105200410
        };
        var target = targets[mapId] || (mapId + 10);
        pi.playPortalSound();
        pi.warp(target, "sp");
        return true;
    } else if (pi.isQuestStarted(30027) || pi.isQuestCompleted(30027)) {
        // 任务30027已开始或已完成：按地图弹出NPC对话
        var npcs = {
            105200500: { id: 1064005, script: "bbbattle" },
            105200600: { id: 1064006, script: "paebattle" },
            105200700: { id: 1064007, script: "nwbattle" },
            105200800: { id: 1064008, script: "blbattle" }
        };
        if (npcs[mapId]) {
            pi.openNpc(npcs[mapId].id, npcs[mapId].script);
            return false;
        } else {
            pi.playerMessage(5, "无法进入该地区");
            return false;
        }
    } else {
        pi.playerMessage(5, "无法进入");
        return false;
    }
}
