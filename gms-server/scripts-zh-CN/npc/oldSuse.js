var status = -1;
var jq=0;
function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode < 0) {
        // 玩家跳过/关闭对话时仍完成任务，避免卡住
		cm.forceCompleteQuest(30004);
        cm.dispose();
        return;
    }
    status++;

    if (status === 0) {
        cm.sendNext("看来卷轴没有问题.\r\n这次又失败了……我真的没办法出去吗……？");
		cm.forceCompleteQuest(30004);

    }  else {
        cm.forceCompleteQuest(30004);
        cm.dispose();
    }
}
