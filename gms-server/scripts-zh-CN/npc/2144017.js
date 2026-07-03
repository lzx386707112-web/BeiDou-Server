/*
    Otherworld altar statue - cut-down Arkarium flow.
*/

var status = -1;
var modeType = "";

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == -1 || mode == 0) {
        cm.dispose();
        return;
    }
    status++;

    var mapId = cm.getPlayer().getMapId();
    if (status == 0) {
        if (mapId == 272020110) {
            modeType = "enter";
            cm.sendYesNo("要进入阿卡伊勒的祭坛吗？");
        } else if (mapId == 272020200) {
            var eim = cm.getEventInstance();
            if (eim != null && eim.isEventCleared()) {
                modeType = "leave";
                cm.sendYesNo("阿卡伊勒已经被击败。要离开祭坛吗？");
            } else {
                modeType = "summon";
                cm.sendYesNo("把手放在石像上，召唤阿卡伊勒吗？");
            }
        } else {
            cm.sendOk("石像没有回应。");
            cm.dispose();
        }
        return;
    }

    if (status == 1) {
        if (modeType == "enter") {
            var currentEim = cm.getPlayer().getEventInstance();
            if (currentEim != null && currentEim.getName().startsWith("ArkariumBattle") && !currentEim.isEventCleared()) {
                var map = currentEim.getMapInstance(272020200);
                cm.getPlayer().changeMap(map, map.getPortal(0));
                cm.dispose();
                return;
            }

            var em = cm.getEventManager("ArkariumBattle");
            if (em == null || !em.startInstance(cm.getPlayer())) {
                cm.sendOk("祭坛的时空还没有稳定，请稍后再试。");
            }
            cm.dispose();
        } else if (modeType == "leave") {
            cm.warp(272020110, 0);
            cm.dispose();
        } else if (modeType == "summon") {
            var eim = cm.getEventInstance();
            if (eim == null) {
                cm.sendOk("这里不是稳定的祭坛空间。");
            } else {
                var beforeCount = cm.countMonster();
                if (eim.getProperty("summoned") == "1" && beforeCount <= 0) {
                    eim.setProperty("summoned", "0");
                }
                if (eim.getProperty("summoned") == "1" || beforeCount > 0) {
                    cm.sendOk("阿卡伊勒已经降临。");
                } else {
                    try {
                        cm.spawnMonster(8860000, 320, -181);
                    } catch (err) {
                        eim.setProperty("summoned", "0");
                        cm.sendOk("阿卡伊勒暂时无法降临，请检查怪物数据。");
                        cm.dispose();
                        return;
                    }
                    if (cm.countMonster() > beforeCount) {
                        eim.setProperty("summoned", "1");
                        cm.mapMessage(5, "阿卡伊勒现身了。");
                    } else {
                        eim.setProperty("summoned", "0");
                        cm.sendOk("阿卡伊勒暂时无法降临，请检查怪物数据。");
                    }
                }
            }
            cm.dispose();
        }
    }
}
