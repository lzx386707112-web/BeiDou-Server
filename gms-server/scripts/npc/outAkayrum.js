/*
	功能:	怪物清场检查 — 无怪物时按所在地图回到对应入口
		地图 272010200 -> 272010100
		地图 272030400 -> 272030300
		其他地图 -> 272010100（保持原行为）
	说明:	放入对应NPC的脚本文件中即可（按NPC ID命名）
*/
var status = 0;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (status >= 0 && mode == 0) {
	cm.dispose();
	return;
    }
    if (mode == 1)
	status++;
    else
	status--;

    if (status == 0) {
	var mobs = cm.getPlayer().getMap().getAllMonsters();
	if (mobs == null || mobs.size() == 0) {
	    var mapId = cm.getPlayer().getMapId();
	    if (mapId == 272010200) {
		cm.warp(272010100);
	    } else if (mapId == 272030400) {
		cm.warp(272030300);
	    } else {
		cm.warp(272010100);
	    }
	    cm.dispose();
	} else {
	    cm.sendOk("现在不是害怕的时候，你一定可以打败他的！");
	    cm.dispose();
	}
    }
}
