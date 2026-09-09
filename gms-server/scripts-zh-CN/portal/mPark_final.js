function grantParkClear(pi) {
    var player = pi.getPlayer();
    player.gainExp(Math.max(player.getLevel() * 120, 1000), true, true, true);
    player.gainMeso(Math.max(player.getLevel() * 80, 1000), true);
    var Calendar = Java.type("java.util.Calendar");
    var weekday = Calendar.getInstance().get(Calendar.DAY_OF_WEEK);
    var medalQuests = [0, 15187, 15181, 15182, 15183, 15184, 15185, 15186];
    var questId = medalQuests[weekday];
    if (questId > 0 && pi.getQuestStatus(questId) == 1) {
        pi.forceCompleteQuest(questId);
    }
    grantParkCoins(pi);
}

function grantParkCoins(pi) {
    var coins = coinsForClear(pi);
    if (coins <= 0) {
        return;
    }
    if (!pi.canHold(4310020, coins)) {
        pi.playerMessage(5, "其他栏已满，未能领取怪物公园纪念币。");
        return;
    }
    pi.gainItem(4310020, coins);
    pi.playerMessage(5, "获得了 " + coins + " 枚怪物公园纪念币。");
}

function coinsForClear(pi) {
    var eim = pi.getPlayer().getEventInstance();
    if (eim != null) {
        var region = eim.getProperty("parkRegion");
        if (region == "MPARK_BASIC") {
            return 1;
        }
        if (region == "MPARK_MIDDLE") {
            return 5;
        }
        if (region == "MPARK_ADVANCED") {
            return 20;
        }
        var start = parseInt(eim.getProperty("course"));
        if (start >= 954103000) {
            return 20;
        }
        if (start == 953020000 || start >= 954030000) {
            return 5;
        }
        return 1;
    }
    return 1;
}

function enter(pi) {
    if (pi.getPlayer().getMap().countMonsters() > 0) {
        pi.playerMessage(5, "必须先消灭这张地图上的所有怪物，才能离开。");
        return false;
    }
    grantParkClear(pi);
    var eim = pi.getPlayer().getEventInstance();
    pi.playPortalSound();
    if (eim != null) {
        eim.stopEventTimer();
        eim.setEventCleared();
        eim.exitPlayer(pi.getPlayer());
    } else {
        pi.warp(951000000, 0);
    }
    return true;
}
