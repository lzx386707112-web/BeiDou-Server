function enter(pi) {
    // 任务31180已完成：被神秘力量送回 272000000
    if (pi.isQuestCompleted(31180)) {
        pi.playerMessage(5, "一股神秘的力量将你送回去了");
        pi.playPortalSound();
        pi.warp(272000000);
        return true;
    }

    // 任务31180未开始且未完成：被神秘力量阻止
    if (!pi.isQuestStarted(31180) && !pi.isQuestCompleted(31180)) {
        pi.playerMessage(5, "一股神秘的力量阻止了你，请回去吧。");
        return false;
    }

    var mapId = pi.getPlayer().getMapId();
    if (mapId == 272020110) {
        // 已经在战斗地图，踩门触发 NPC 战斗，不再传送
        pi.openNpc(2144017);
        return false;
    }
    // 其他地图踩门，传送进 272020110
    pi.openNpc(2144017);
    return true;
}
