/*
	名字:	裂缝传送确认 NPC
	地图:	3005427
	功能:	询问是否进入裂缝，是→272000000，否→提示后结束
	门控:	任务31165已开始(isQuestActive)或已完成(isQuestFinished)才允许进入
*/
var status = 0;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (status >= 0 && mode == 0) {
	cm.sendOk("等你准备好了再来。");
	cm.dispose();
	return;
    }
    if (mode == 1)
	status++;
    else
	status--;

    if (status == 0) {
	cm.sendYesNo("准备好进入裂缝了吗？");
    } else if (status == 1) {
	// 能走到这里说明点的是"是"(mode==1)
	if (!(cm.isQuestActive(31165) || cm.isQuestCompleted(31165))) {
	    cm.sendOk("这里面很危险，快走开。");
	    cm.dispose();
	    return;
	}
	cm.warp(272000000, 0);
	cm.dispose();
    }
}