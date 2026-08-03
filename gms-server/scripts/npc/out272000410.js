/*
	功能:	怪物清场检查 — 272000400，否则提示无法离开
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
	    cm.warp(272000400);
	    cm.dispose();
	} else {
	    cm.sendOk("别想逃，你必须先打败我！");
	    cm.dispose();
	}
    }
}
