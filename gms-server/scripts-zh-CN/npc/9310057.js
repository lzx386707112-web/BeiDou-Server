var rewards = Array(2000005, 1140001, 1141001, 2100005, 2100006, 2100007, 2100008, 2101000, 2101001);//物品代码
var expires = Array(-1, 10, 30, 30, 30, 30, 30, 60, 60);//时间
var quantity = Array(5, 1, 1, 1, 1, 1, 1, 1, 1);//数量
var needed = Array(30, 60, 60, 25, 30, 35, 40, 45, 50, 55);//需要物品的数量
var gender = Array(2, 0, 1, 2, 2, 2, 2, 2, 2);//性别
var status;
var map;

function start() {
	status = -1;
	action(1, 0, 0);
}


function action(mode, type, selection) {
	if (mode == 1) {
		status++;
	} else {
		if (status == 0) {
			cm.dispose();
		}
		status--;
	}
	/*if (status == 0) {
		for (var i = 1442070; i < 1442088; i++) {
		cm.removeAll(i);
	}*/
	switch (cm.getPlayer().getMapId()) {
		case 100000000:
		case 101000000:
		case 102000000:
		case 103000000:
		case 104000000:
		case 120000000:
		case 211000000:
		case 250000000:
		case 220000000:
		case 200000000:
		case 261000000:
		case 500000000:
		case 600000000:
		case 680000000:
		case 701000100:
		case 702000000:
		case 800000000:
			if (status == 0) {
				cm.sendSimple("你好，我是#b蘑菇博士#k！\r\n\r\n#L0#我想兑换物品#l");
			} else if (status == 1) {
				var selStr = "\r\n\r\n#b";
				for (var i = 0; i < rewards.length; i++) {
					if (rewards[i] == 1141001 && cm.getPlayer().isMale())
						continue;
					if (rewards[i] == 1140001 && !cm.getPlayer().isMale())
						continue;
					selStr += "#L" + i + "#兑换#v" + rewards[i] + "##z" + rewards[i] + "# x " + quantity[i] + " #r(" + needed[i] + " 优秀印章)#b#l\r\n";
				}
				cm.sendSimple(selStr);
			} else if (status == 2) {
				if (!cm.haveItem(4001137, needed[selection])) {
					cm.sendNext("您没有#b#t4001137##k");
				} else if (!cm.canHold(rewards[selection], 1)) {
					cm.sendNext("请空出一些空间。");
				} else {
					cm.gainItem(4001137, -needed[selection]);
					cm.gainItem(rewards[selection], quantity[selection]);

				}
				cm.dispose();
			}
			break;
	}

}
