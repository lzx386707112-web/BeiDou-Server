/*
	功能:	怪物清场检查 — 地图内无怪物时传送105200000，否则提示无法离开
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
	    cm.warp(105200000);
	    cm.dispose();
	} else {
	    cm.sendOk("还有敌人在场地里，无法安全地离开。请先打败敌人！");
	    cm.dispose();
	}
    }
}
