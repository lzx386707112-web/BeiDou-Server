var bossMaps = Array(
    Array(262030300, 500000, "希拉                               #r（消耗50万金币）#b", 8870000, -1, 1092, 196),
    Array(262031300, 500000, "白发希拉                       #r（消耗50万金币）#b", 8870200, -1, 1092, 196),
    Array(450010100, 500000, "觉醒希拉                       #r（消耗50万金币）#b", 8880400, -1, 855, 266),
    Array(450009400, 500000, "亲卫队长敦凯尔            #r（消耗50万金币）#b", 8645009, -1, -1, -157),
    Array(900000207, 500000, "守护天使绿水灵            #r（消耗50万金币）#b", 8880700, -1, 703, -1394),
    Array(410002060, 500000, "监视者卡洛斯                #r（消耗50万金币）#b", 8880803, -1, 900, 325),
    Array(410002061, 500000, "沦陷的监视者卡洛斯    #r（消耗50万金币）#b", 8880820, 410002060, 900, 325)
);

var entryItems = Array(
    Array(4000019, 500),
    Array(2210006, 1)
);

function start() {
    if (cm.getPlayer().getLevel() < 100) {
        cm.sendOk("达到 100 级后才可以使用高级 Boss 传送。");
        cm.dispose();
        return;
    }

    var text = "#e#b高级 Boss 传送#k#n\r\n\r\n";
    for (var i = 0; i < bossMaps.length; i++) {
        text += "#L" + i + "#" + bossMaps[i][2] + "#l\r\n";
    }
    cm.sendNextSelectLevel("Boss", text);
}

function levelBoss(selection) {
    if (selection < 0 || selection >= bossMaps.length) {
        cm.dispose();
        return;
    }

    var config = bossMaps[selection];
    var mapId = config[0];
    var cost = config[1];
    var bossId = config[3];
    var fallbackMapId = config[4];
    var bossX = config[5];
    var bossY = config[6];

    if (cm.getPlayer().getMeso() < cost) {
        cm.sendOk("您的金币不足，无法传送！需要 " + cost + " 金币。");
        cm.dispose();
        return;
    }
    if (!hasEntryItems()) {
        cm.sendOk("进入该 Boss 地图除 " + cost + " 金币外，还需要：\r\n" + getEntryItemText());
        cm.dispose();
        return;
    }

    var targetMap = cm.getMap(mapId);
    if (targetMap == null && fallbackMapId != null && fallbackMapId > 0) {
        mapId = fallbackMapId;
        targetMap = cm.getMap(mapId);
    }
    if (targetMap == null) {
        cm.sendOk("目标地图 " + mapId + " 未被当前服务端加载。"
            + getMapResourceStatus(mapId)
            + "\r\n请按上面的绝对路径检查补丁覆盖层级，并完全重启服务端。");
        cm.dispose();
        return;
    }

    if (targetMap.getMonsterById(bossId) == null) {
        const LifeFactory = Java.type("org.gms.server.life.LifeFactory");
        const Point = Java.type("java.awt.Point");
        var boss = LifeFactory.getMonster(bossId);
        if (boss == null) {
            cm.sendOk("Boss 数据 " + bossId + " 未被当前服务端加载。"
                + "\r\n普通WZ：" + getServerResourceStatus("wz/Mob.wz/" + bossId + ".img.xml")
                + "\r\n语言WZ：" + getServerResourceStatus("wz-zh-CN/Mob.wz/" + bossId + ".img.xml")
                + "\r\n请按上面的绝对路径检查补丁覆盖层级，并完全重启服务端。");
            cm.dispose();
            return;
        }
        targetMap.spawnMonsterOnGroundBelow(boss, new Point(bossX, bossY));
    }

    cm.gainMeso(-cost);
    changeEntryItems(-1);
    cm.getPlayer().saveLocationOnWarp();

    var targetPortal = targetMap.getPortal("bossRetry");
    if (targetPortal != null) {
        cm.getPlayer().changeMap(targetMap, targetPortal.getPosition());
    } else {
        cm.warp(mapId, 0);
    }
    cm.dispose();
}

function hasEntryItems() {
    for (var i = 0; i < entryItems.length; i++) {
        if (!cm.haveItem(entryItems[i][0], entryItems[i][1])) {
            return false;
        }
    }
    return true;
}

function changeEntryItems(multiplier) {
    for (var i = 0; i < entryItems.length; i++) {
        cm.gainItem(entryItems[i][0], entryItems[i][1] * multiplier);
    }
}

function getEntryItemText() {
    return "#v4000019##z4000019# ×500\r\n#v2210006##z2210006# ×1";
}

function getServerResourceStatus(relativePath) {
    const File = Java.type("java.io.File");
    var file = new File(relativePath);
    return file.getAbsolutePath() + "（" + (file.isFile() ? "存在" : "不存在") + "）";
}

function getMapResourceStatus(mapId) {
    var area = Math.floor(mapId / 100000000);
    var relative = "Map.wz/Map/Map" + area + "/" + mapId + ".img.xml";
    return "\r\n普通WZ：" + getServerResourceStatus("wz/" + relative)
        + "\r\n语言WZ：" + getServerResourceStatus("wz-zh-CN/" + relative);
}
