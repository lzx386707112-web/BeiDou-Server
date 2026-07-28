var status = -1;

function start() {
	action(1, 0, 0);
}

function action(mode, type, selection) {
	if (mode != 1 || status >= 0) {
		cm.dispose();
		return;
	}
	status++;
	cm.sendOk("红鸾宫相关路线已关闭。");
}
