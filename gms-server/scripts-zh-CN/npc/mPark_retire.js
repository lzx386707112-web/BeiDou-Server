/**
 * 9071005 / mPark_retire — Spiegelmann inside Monster Park stages.
 * TMS: this NPC is for giving up. Next stage is the upper next00 portal
 * after the map is cleared. The old client often misses that portal, so
 * this script also warps to the next map once no monsters remain.
 */

var status = -1;
var choice = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function isLastStage(mapId) {
    return (mapId % 1000) === 500;
}

function grantClear(cm) {
    var player = cm.getPlayer();
    player.gainExp(Math.max(player.getLevel() * 120, 1000), true, true, true);
    player.gainMeso(Math.max(player.getLevel() * 80, 1000), true);
    var Calendar = Java.type("java.util.Calendar");
    var weekday = Calendar.getInstance().get(Calendar.DAY_OF_WEEK);
    var medalQuests = [0, 15187, 15181, 15182, 15183, 15184, 15185, 15186];
    var questId = medalQuests[weekday];
    if (questId > 0 && cm.getQuestStatus(questId) == 1) {
        cm.forceCompleteQuest(questId);
    }
}

function leavePark(cm) {
    var eim = cm.getEventInstance();
    if (eim != null) {
        eim.exitPlayer(cm.getPlayer());
    } else {
        cm.warp(951000000, 0);
    }
}

function goNext(cm) {
    if (cm.getMap().countMonsters() > 0) {
        cm.sendOk("必须先消灭这张地图上的所有怪物。");
        return;
    }
    var next = cm.getMapId() + 100;
    var eim = cm.getEventInstance();
    var target = eim != null ? eim.getMapInstance(next) : cm.getWarpMap(next);
    if (target == null) {
        cm.sendOk("没有下一阶段。");
        return;
    }
    cm.getPlayer().changeMap(target, target.getPortal(0));
}

function finishPark(cm) {
    if (cm.getMap().countMonsters() > 0) {
        cm.sendOk("必须先消灭这张地图上的所有怪物。");
        return;
    }
    grantClear(cm);
    var eim = cm.getEventInstance();
    if (eim != null) {
        eim.stopEventTimer();
        eim.setEventCleared();
        eim.exitPlayer(cm.getPlayer());
    } else {
        cm.warp(951000000, 0);
    }
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        var leftover = cm.getMap().countMonsters();
        var last = isLastStage(cm.getMapId());
        var text = "如果想要离开这地方的话，请和我对话。\r\n\r\n";
        text += "玩法：每张图清掉全部怪物后，走#b上方传送门#k进入下一关。一共 6 关，限时 10 分钟。\r\n";
        if (leftover > 0) {
            text += "当前还剩 #r" + leftover + "#k 只怪物。\r\n#b";
            text += "#L0#离开怪物公园#l\r\n";
            text += "#L1#下一关怎么走？#l";
        } else if (last) {
            text += "本关怪物已经清空。\r\n#b";
            text += "#L0#离开怪物公园#l\r\n";
            text += "#L2#领取奖励并离开#l";
        } else {
            text += "本关怪物已经清空。\r\n#b";
            text += "#L0#离开怪物公园#l\r\n";
            text += "#L2#送我去下一阶段#l";
        }
        cm.sendSimple(text);
    } else if (status == 1) {
        choice = selection;
        if (choice == 0) {
            cm.sendYesNo("确定要离开怪物公园吗？进度不会保留。");
        } else if (choice == 1) {
            cm.sendOk("先打完这张图的怪物。清空后走到地图#b上方#k的传送门就能进下一关。如果找不到门，清空后再来找我，我可以送你过去。");
            cm.dispose();
        } else if (choice == 2) {
            if (isLastStage(cm.getMapId())) {
                finishPark(cm);
            } else {
                goNext(cm);
            }
            cm.dispose();
        } else {
            cm.dispose();
        }
    } else if (status == 2) {
        if (choice == 0) {
            leavePark(cm);
        }
        cm.dispose();
    }
}
