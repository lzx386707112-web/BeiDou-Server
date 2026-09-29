//Gachaphon

importPackage(net.sf.odinms.client);



var status = 0;
var chance1 = Math.floor(Math.random()*200+1);
var chance2 = Math.floor(Math.random()*100);
var chance3 = (Math.floor(Math.random()*20)+1);
var chance4 = Math.floor(Math.random()*10+1);
var itemchance = chance1 + chance2 + chance3 * chance4;
var itemamount = Math.floor(Math.random()*5+2);


function start() {
	status = -1;
	action(1, 0, 0);
}


function action(mode, type, selection) {
	if (mode == -1) {
		cm.dispose();
	} else {
		if (status >= 2 && mode == 0) {
			cm.sendOk("哇.在活动中你的运气很好.祝你下次好运~!");
			cm.dispose();
			return;
		}
		if (mode == 1)
			status++;
		else
			status--;
		if (status == 0) {
				cm.sendNext("我是高级快乐百宝箱.\r\n#e如果你有#e #b#v4110010##k一张#b豆豆票#k\r\n可以在我这里随机换取物品哦~！\r\n\r\n这里只有#r极其珍贵的装备#k，说不定还能拿到#r传说中的神器#k！");
			}
		else if (status == 1) {
                        if (cm.haveItem(4110010)) {
			cm.sendYesNo("我看见你有换取道具了,你要使用它?");
			}
			else if (!cm.haveItem(4110010)) {
			cm.sendOk("你身上没有兑换道具，#b魂#k交代我不能帮你!.");
			cm.dispose();
			}
		}
		else if (status == 2) {
			cm.gainItem(4110010, -1);

			
			
			if ((itemchance >= 1) && (itemchance <= 71)) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的  高级百宝券N张!!!");
			cm.gainItem(5220010, itemamount);
			}
			else if (itemchance == 72) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒匿踪盾 !");
			cm.gainItem(1092059  , 1);
			}
			else if (itemchance == 73) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒狂鲨锯 !");
			cm.gainItem(1332073   , 1);
			}
			else if (itemchance == 74) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒断首刃 !");
			cm.gainItem(1332074    , 1);
			}
			else if (itemchance == 75) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒大悲赋 !");
			cm.gainItem(1472068   , 1);
			}
			else if (itemchance == 76) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒海王星 !");
			cm.gainItem(1002780    , 1);
			}
			else if (itemchance == 77) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒霸七海 !");
			cm.gainItem(1052159   , 1);
			}
			else if (itemchance == 78) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒定海靴 !");
			cm.gainItem(1072359    , 1);
			}
			else if (itemchance == 79) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒抚浪手套 !");
			cm.gainItem(1082238    , 1);
			}	
			else if (itemchance == 80) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒孔雀翎 !");
			cm.gainItem(1482023   , 1);
			}	
			else if (itemchance == 81) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒凤凰铳 !");
			cm.gainItem(1492023   , 1);
			}
			else if (itemchance == 82) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的祝福卷!");
			cm.gainItem(2340000     , 1);
			}
			else if (itemchance == 83) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的平衡的狂怒!");
			cm.gainItem(2070018    , 1);
			}	
			else if (itemchance == 84) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的黑龙项环!");
			cm.gainItem(1122000    , 1);
			}
			else if (itemchance == 90) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的扎昆头盔!");
			cm.gainItem(1002357    , 1);
			}
			else if (itemchance == 91) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的暴力熊头盔!");
			cm.gainItem(1002905    , 1);
			}
			else if (itemchance == 92) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的心疤狮王!");
			cm.gainItem(1002906   , 1);
			}
			else if (itemchance == 93) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的天仙帽!");
			cm.gainItem(1002972    , 1);
			}
			else if (itemchance == 94) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的黄金披风!");
			cm.gainItem(1102163   , 1);
			}
			else if (itemchance == 95) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得神卷  休彼德蔓的珠子!");
			cm.gainItem(2041211  , 1);
			}
			else if (itemchance == 96) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得神卷  何露斯之眼!");
			cm.gainItem(2041212 , 1);
			}
			else if (itemchance == 97) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的蓝带!");
			cm.gainItem(1082246   , 1);
			}
			else if (itemchance == 98) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的芬达罐!");
			cm.gainItem(1052150   , 1);
			}
			else if (itemchance == 99) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的泡泡戒指!");
			cm.gainItem(1112500  , 1);
			}
			else if (itemchance == 100) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的结婚戒指!");
                        cm.gainItem(1112804   , 1);
			}
			else if (itemchance == 101) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的热情剑盾!");
			cm.gainItem(1092049  , 1);
			}
			else if (itemchance == 102) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的爆炎之杖!");
			cm.gainItem(1372039  , 1);
			}
			else if (itemchance == 103) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的剧毒之杖!");
			cm.gainItem(1372040   , 1);
			}
			else if (itemchance == 104) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的寒冰之杖!");
			cm.gainItem(1372041  , 1);
			}
			else if (itemchance == 105) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的狂雷之杖!");
			cm.gainItem(1372042  , 1);
			}
			else if (itemchance == 106) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的朱雀长杖!");
			cm.gainItem(1382049   , 1);
			}
			else if (itemchance == 107) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的玄武长杖!");
			cm.gainItem(1382050   , 1);
			}
			else if (itemchance == 108) {
 cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的白虎长杖!");
			cm.gainItem(1382051   , 1);
			}
			else if (itemchance == 109) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得青龙长杖!");
			cm.gainItem(1382052, 1);
			}
			else if (itemchance == 110) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得月牙标!");
			cm.gainItem(2070007, 1);
			}
			else if (itemchance == 111) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得穿甲弹!");
			cm.gainItem(2330005, 1);
			}
			else if (itemchance == 112) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得火红魔方!");
			cm.gainItem(2331000 , 1);
			}
			else if (itemchance == 113) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得冰蓝魔方!");
			cm.gainItem(2332000 , 1);
			}
			else if (itemchance == 114) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得匹诺曹的鼻子!");
			cm.gainItem(1012058 , 1);
			}
			else if (itemchance == 115) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得匹诺曹的鼻子!");
			cm.gainItem(1012059 , 1);
			}
			else if (itemchance == 116) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得匹诺曹的鼻子!");
			cm.gainItem(1012060 , 1);
			}
			else if (itemchance == 117) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得匹诺曹的鼻子!");
			cm.gainItem(1012061 , 1);
			}
			else if (itemchance == 118) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012064 , 1);
			}
			else if (itemchance == 119) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012065, 1);
			}
			else if (itemchance == 120) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012066, 1);
			}
			else if (itemchance == 121) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012067, 1);
			}
			else if (itemchance == 122) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012068, 1);
			}
			else if (itemchance == 123) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得印度僧印!");
			cm.gainItem(1012069, 1);
			}
			else if (itemchance == 124) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 草莓雪糕!");
			cm.gainItem(1012070 , 1);
			}
			else if (itemchance == 125) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 巧克力雪糕!");
			cm.gainItem(1012071 , 1);
			}
			else if (itemchance == 126) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 甜瓜雪糕!");
			cm.gainItem(1012072 , 1);
			}
			else if (itemchance == 127) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 西瓜雪糕!");
			cm.gainItem(1012073 , 1);
			}
			else if (itemchance == 128) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小白鼠假面!");
			cm.gainItem(1012084 , 1);
			}
			else if (itemchance == 129) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 微笑的假面!");
			cm.gainItem(1012076 , 1);
			}
			else if (itemchance == 130) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 哭泣的假面!");
			cm.gainItem(1012077 , 1);
			}
			else if (itemchance == 131) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 生气的假面!");
			cm.gainItem(1012078 , 1);
			}
			else if (itemchance == 132) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 郁闷的假面!");
			cm.gainItem(1012079 , 1);
			}
			else if (itemchance == 133) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 假面绅士面具!");
			cm.gainItem(1012081 , 1);
			}
			else if (itemchance == 134) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小白鼠试剂盒!");
			cm.gainItem(1012086 , 1);
			}
			else if (itemchance == 135) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小白鼠假面!");
			cm.gainItem(1012087 , 1);
			}
			else if (itemchance == 136) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小白鼠假面!");
			cm.gainItem(1012088 , 1);
			}
			else if (itemchance == 137) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小白鼠假面!");
			cm.gainItem(1012106 , 1);
			}
			else if (itemchance == 138) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 符咒!");
			cm.gainItem(1012091, 1);
			}
			else if (itemchance == 139) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 符咒!");
			cm.gainItem(1012092, 1);
			}
			else if (itemchance == 140) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 符咒!");
			cm.gainItem(1012093, 1);
			}
			else if (itemchance == 141) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 符咒!");
			cm.gainItem(1012094, 1);
			}
			else if (itemchance == 142) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 符咒!");
			cm.gainItem(1012095, 1);
			}
			else if (itemchance == 143) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫叶!");
			cm.gainItem(1012098 , 1);
			}
			else if (itemchance == 144) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫叶!");
			cm.gainItem(1012101 , 1);
			}
			else if (itemchance == 145) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫叶!");
			cm.gainItem(1012102 , 1);
			}
			else if (itemchance == 146) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫叶!");
			cm.gainItem(1012103 , 1);
			}
			else if (itemchance == 147) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（新加坡）!");
			cm.gainItem(1012115, 1);
			}
			else if (itemchance == 148) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（新加坡）!");
			cm.gainItem(1012116, 1);
			}
			else if (itemchance == 149) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（新加坡）!");
			cm.gainItem(1012117, 1);
			}
			else if (itemchance == 150) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（马来西亚）!");
			cm.gainItem(1012118, 1);
			}
			else if (itemchance == 151) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（马来西亚）!");
			cm.gainItem(1012119, 1);
			}
			else if (itemchance == 152) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 面具（马来西亚）!");
			cm.gainItem(1012120, 1);
			}
			else if (itemchance == 153) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 鸡嘴!");
			cm.gainItem(1012132 , 1);
			}
			else if (itemchance == 154) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 猪鼻!");
			cm.gainItem(1012135 , 1);
			}
			else if (itemchance == 155) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 星之印!"); 
			cm.gainItem(1012137 , 1);
			}
			else if (itemchance == 156) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 巧克力冰激凌!");
			cm.gainItem(1012138 , 1);
			}
			else if (itemchance == 157) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 樱印!");
			cm.gainItem(1012139  , 1);
			}
			else if (itemchance == 158) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 星印!");
			cm.gainItem(1012140 , 1);
			}
			else if (itemchance == 159) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 大鼻子!");
			cm.gainItem(1012146 , 1);
			}
			else if (itemchance == 160) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫之印!");
			cm.gainItem(1012148 , 1);
			}
			else if (itemchance == 161) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 生日蛋糕!");
			cm.gainItem(1012157 , 1);
			}
			else if (itemchance == 162) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 猫头鹰!");
			cm.gainItem(1022047 , 1);
			}
			else if (itemchance == 163) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 狸猫!");
			cm.gainItem(1022058 , 1);
			}
			else if (itemchance == 164) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 狐猴!");
			cm.gainItem(1022060 , 1);
			}
                        else if (itemchance == 165) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小眼镜!");
			cm.gainItem(1022088, 1);
			}
			else if (itemchance == 166) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 小眼镜!");
			cm.gainItem(1022089, 1);
			}
			else if (itemchance == 167) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 勇气耳环!");
			cm.gainItem(1032030, 1);
			}
			else if (itemchance == 168) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 永恒金盾坠!");
			cm.gainItem(1032031 , 1);
			}
			else if (itemchance == 169) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 蓝水晶耳环!");
			cm.gainItem(1032037 , 1);
			}
			else if (itemchance == 170) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 水晶叶子耳环!");
			cm.gainItem(1032048 , 1);
			}
			else if (itemchance == 171) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 耳机!");
			cm.gainItem(1032055, 1);
			}
			else if (itemchance == 172) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 耳机!");
			cm.gainItem(1032056, 1);
			}
			else if (itemchance == 173) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 耳机!");
			cm.gainItem(1032057, 1);
			}
			else if (itemchance == 174) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 耳机!");
			cm.gainItem(1032058, 1);
			}
			else if (itemchance == 175) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 灰环!");
			cm.gainItem(1032059 , 1);
			}
			else if (itemchance == 176) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 休彼德蔓的项链!");
			cm.gainItem(1122007 , 1);
			}
			else if (itemchance == 177) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 何露斯之眼!");
			cm.gainItem(1122010 , 1);
			}
			else if (itemchance == 178) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 封印的永恒玉佩!");
			cm.gainItem(1122011 , 1);
			}
			else if (itemchance == 179) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 副银星!");
			cm.gainItem(1122014 , 1);
			}
			else if (itemchance == 180) {
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 枫叶围巾!"); 
			cm.gainItem(1122015 , 1);
			}
			else if (itemchance == 181) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 经验吊坠!");
			cm.gainItem(1122017 , 1);
			}
			else if (itemchance == 182) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 温暖的围脖!");
			cm.gainItem(1122018 , 1);
			}
			else if (itemchance == 190) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 山炮!");
			cm.gainItem(1302104, 1);
			}
			else if (itemchance == 191) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 叶刃!");
			cm.gainItem(1332069, 1);
			}
			else if (itemchance == 192) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 绝影尖嘴刃!");
			cm.gainItem(1332080 , 1);
			}
			else if (itemchance == 193) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 暗乌之剑 !");
			cm.gainItem(1402049 , 1);
			}
			else if (itemchance == 194) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世 黎明乌之翼!");
			cm.gainItem(1402050, 1);
			}
			else if (itemchance == 214) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  休彼德蔓的项链!");
			cm.gainItem(1122058, 1);
			}
			else if (itemchance == 215) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  真扎昆头盔!");
			cm.gainItem(1002390 , 1);
			}
			else if (itemchance == 216) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  真扎昆头盔!");
			cm.gainItem(1002430 , 1);
			}
			else if (itemchance == 217) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  小白鼠发带 !");
			cm.gainItem(1002737 , 1);
			}
			else if (itemchance == 218) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  无线耳机!");
			cm.gainItem(1002797 , 1);
			}
			else if (itemchance == 219) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  暴力熊头盔!");
			cm.gainItem(1002926, 1);
			}
			else if (itemchance == 220) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  心疤狮王!");
			cm.gainItem(1002927, 1);
			}
			else if (itemchance == 221) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  小鸡快跑!");
			cm.gainItem(1002946 , 1);
			}
			else if (itemchance == 222) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  品克缤头盖!");
			cm.gainItem(1002971 , 1);
			}
			else if (itemchance == 223) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  兽皮披风!");
			cm.gainItem(1102064  , 1);
			}
			else if (itemchance == 224) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  月食披风!");
			cm.gainItem(1102078  , 1);
			}
			else if (itemchance == 225) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  绿斗士披风!");
			cm.gainItem(1102087 , 1);
			}
			else if (itemchance == 226) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  阿莫斯皇家披风!");
			cm.gainItem(1102099 , 1);
			}
			else if (itemchance == 227) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  阿莫斯圣灵披风!");
			cm.gainItem(1102100 , 1);
			}
			else if (itemchance == 228) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  传说的伊莱亚披风1!");
			cm.gainItem(1102101 , 1);
			}
			else if (itemchance == 229) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  传说的伊莱亚披风2!");
			cm.gainItem(1102102 , 1);
			}
			else if (itemchance == 230) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  传说的伊莱亚披风3!");
			cm.gainItem(1102103 , 1);
			}
			else if (itemchance == 231) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  天狼星斗篷!");
			cm.gainItem(1102145 , 1);
			}
			else if (itemchance == 232) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  泽塔角!");
			cm.gainItem(1102146 , 1);
			}
			else if (itemchance == 233) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  风筝!");
			cm.gainItem(1102161 , 1);
			}
			else if (itemchance == 234) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  塔鲁精神佛得角!");
			cm.gainItem(1102165 , 1);
			}
			else if (itemchance == 235) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  暗黑围巾!");
			cm.gainItem(1102170 , 1);
			}
			else if (itemchance == 236) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  纪念气球!");
			cm.gainItem(1102173  , 1);
			}
			else if (itemchance == 237) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  腐败斗篷!");
			cm.gainItem(1102193, 1);
			}
			else if (itemchance == 238) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  莫扎特的寿衣!");
			cm.gainItem(1102194 , 1);
			}
			else if (itemchance == 239) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙纹战甲 !");
			cm.gainItem(1040120, 1);
			}
			else if (itemchance == 240) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙纹战甲 !");
			cm.gainItem(1041122, 1);
			}
			else if (itemchance == 241) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  侠盗手套 !");
			cm.gainItem(1082135, 1);
			}
			else if (itemchance == 242) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  幻光手套 !");
			cm.gainItem(1082142, 1);
			}
			else if (itemchance == 243) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  幻魔手套 !");
			cm.gainItem(1082151, 1);
			}
			else if (itemchance == 244) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  条纹手套 !");
			cm.gainItem(1082158, 1);
			}
			else if (itemchance == 245) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  红猎人手套 !");
			cm.gainItem(1082163 , 1);
			}
			else if (itemchance == 246) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  蓝色元素手套 !");
			cm.gainItem(1082164 , 1);
			}
			else if (itemchance == 247) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黑色格丽娜手套 !");
			cm.gainItem(1082167 , 1);
			}
			else if (itemchance == 248) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  青龙手套 !");
			cm.gainItem(1082168 , 1);
			}
			else if (itemchance == 249) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  女神的法链 !");
			cm.gainItem(1082232, 1);
			}
			else if (itemchance == 250) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  飞羽服 !");
			cm.gainItem(1050106, 1);
			}
			else if (itemchance == 251) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  幻魔长袍 !");
			cm.gainItem(1050102, 1);
			}
			else if (itemchance == 252) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  香菇 !");
			cm.gainItem(1382016, 1);
			}
			else if (itemchance == 253) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  祭司长袍 !");
			cm.gainItem(1051094, 1);
			}
			else if (itemchance == 254) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  幻魔长袍 !");
			cm.gainItem(1051101, 1);
			}
			else if (itemchance == 255) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  飞羽服 !");
			cm.gainItem(1051105, 1);
			}
			else if (itemchance == 256) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  红色斗篷 !");
			cm.gainItem(1052071 , 1);
			}
			else if (itemchance == 257) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黑色格丽纳 !");
			cm.gainItem(1052072 , 1);
			}
			else if (itemchance == 258) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  蓝龙装甲 !");
			cm.gainItem(1052075 , 1);
			}
			else if (itemchance == 259) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  船长服  !");
			cm.gainItem(1052131  , 1);
			}
			else if (itemchance == 260) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  海盗大衣  !");
			cm.gainItem(1052134 , 1);
			}
			else if (itemchance == 261) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  boss服!");
			cm.gainItem(1052148 , 1);
			}
			else if (itemchance == 262) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世   boss服!");
			cm.gainItem(1052149 , 1);
			}
			else if (itemchance == 263) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  最强工作人员套装!");
			cm.gainItem(1052167 , 1);
			}
			else if (itemchance == 264) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  奶粉袋!");
			cm.gainItem(1052184 , 1);
			}
			else if (itemchance == 265) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙纹裤 !");
			cm.gainItem(1060109, 1);
			}
			else if (itemchance == 266) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙纹裤 !");
			cm.gainItem(1061121, 1);
			}
			else if (itemchance == 267) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  月石环1克拉!");
			cm.gainItem(1112300, 1);
			}
			else if (itemchance == 268) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  月石环2克拉!");
			cm.gainItem(1112301, 1);
			}
			else if (itemchance == 269) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  月石环3克拉!");
			cm.gainItem(1112302, 1);
			}
			else if (itemchance == 270) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  闪耀之星环2克拉!");
			cm.gainItem(1112303, 1);
			}
			else if (itemchance == 271) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  闪耀之星环2克拉!");
			cm.gainItem(1112304, 1);
			}
			else if (itemchance == 272) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  闪耀之星环3克拉!");
			cm.gainItem(1112305, 1);
			}
			else if (itemchance == 273) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  金心环1克拉!");
			cm.gainItem(1112306, 1);
			}
			else if (itemchance == 274) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  金心环2克拉!");
			cm.gainItem(1112307, 1);
			}
			else if (itemchance == 275) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  金心环3克拉!");
			cm.gainItem(1112308, 1);
			}
			else if (itemchance == 276) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  银翼环1克拉!");
			cm.gainItem(1112309, 1);
			}
			else if (itemchance == 277) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  银翼环2克拉!");
			cm.gainItem(1112310, 1);
			}
			else if (itemchance == 278) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  银翼环3克拉!");
			cm.gainItem(1112311, 1);
			}
			else if (itemchance == 279) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  心环!");
			cm.gainItem(1112400 , 1);
			}
			else if (itemchance == 280) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  臂盾 !");
			cm.gainItem(1092036 , 1);
			}
			else if (itemchance == 281) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  铁甲盾牌 !");
			cm.gainItem(1092042 , 1);
			}
			else if (itemchance == 282) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  冒险岛魔法师盾牌!");
			cm.gainItem(1092045 , 1);
			}
			else if (itemchance == 283) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  冒险岛战士盾牌 !");
			cm.gainItem(1092046 , 1);
			}
			else if (itemchance == 284) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  冒险岛飞侠盾牌 !");
			cm.gainItem(1092047 , 1);
			}
			else if (itemchance == 285) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  王盾 !");
			cm.gainItem(1092048 , 1);
			}
			else if (itemchance == 289) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  冷艳剑盾  !");
			cm.gainItem(1092050 , 1);
			}
			else if (itemchance == 290) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黑凤凰盾 !");
			cm.gainItem(1092052 , 1);
			}
			else if (itemchance == 291) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  鲜橙多!");
			cm.gainItem(1092054 , 1);
			}
			else if (itemchance == 292) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  可口可乐盾 !");
			cm.gainItem(1092055 , 1);
			}
			else if (itemchance == 293) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  青龙盾牌!");
			cm.gainItem(1092060 , 1);
			}
			else if (itemchance == 294) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  十字盾 !");
			cm.gainItem(1092061 , 1);
			}
			else if (itemchance == 295) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  王盾 !");
			cm.gainItem(1092066 , 1);
			}
			else if (itemchance == 296) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  王盾 !");
			cm.gainItem(1092048 , 1);
			}
			else if (itemchance == 297) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  蓝色元素鞋 !");
			cm.gainItem(1072268 , 1);
			}
			else if (itemchance == 298) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  红猎人鞋 !");
			cm.gainItem(1072269 , 1);
			}
			else if (itemchance == 299) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黑格丽纳鞋 !");
			cm.gainItem(1072272 , 1);
			}
			else if (itemchance == 300) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  青龙长鞋 !");
			cm.gainItem(1072273 , 1);
			}
			else if (itemchance == 301) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  赤羚龙 !");
			cm.gainItem(1902002 , 1);
			}
			else if (itemchance == 302) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  魔毯!");
			cm.gainItem(1902003 , 1);
			}
			else if (itemchance == 303) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  木马!");
			cm.gainItem(1902004 , 1);
			}
			else if (itemchance == 304) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  母鸵鸟!");
			cm.gainItem(1902005 , 1);
			}
			else if (itemchance == 305) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  公鸵鸟!");
			cm.gainItem(1902006 , 1);
			}
			else if (itemchance == 306) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  青蛙王子!");
			cm.gainItem(1902008  , 1);
			}
			else if (itemchance == 307) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  天鸟!");
			cm.gainItem(1902007 , 1);
			}
			else if (itemchance == 308) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  蹦蹦鸟!");
			cm.gainItem(1902009 , 1);
			}
			else if (itemchance == 309) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  小龟龟!");
			cm.gainItem(1902011 , 1);
			}
			else if (itemchance == 310) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  天山雪人!");
			cm.gainItem(1902012 , 1);
			}
			else if (itemchance == 311) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  母牛!");
			cm.gainItem(1902013 , 1);
			}
			else if (itemchance == 312) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  玩具坦克!");
			cm.gainItem(1902014 , 1);
			}
			else if (itemchance == 313) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  小灰狼 !");
			cm.gainItem(1902015 , 1);
			}
			else if (itemchance == 314) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世   疾风狼!");
			cm.gainItem(1902016 , 1);
			}
			else if (itemchance == 315) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  雷觉狼!");
			cm.gainItem(1902017 , 1);
			}
			else if (itemchance == 316) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  银魂狼!");
			cm.gainItem(1902018 , 1);
			}
			else if (itemchance == 317) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  鳄鱼王!");
			cm.gainItem(1902019 , 1);
			}
			else if (itemchance == 318) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  玩具熊!");
			cm.gainItem(1902020 , 1);
			}
			else if (itemchance == 319) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  机达!");
			cm.gainItem(1902021 , 1);
			}
			else if (itemchance == 320) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  拉风摩托!");
			cm.gainItem(1902022 , 1);
			}
			else if (itemchance == 321) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  F1赛车!");
			cm.gainItem(1902023 , 1);
			}
			else if (itemchance == 322) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  天马行空!");
			cm.gainItem(1902024 , 1);
			}
			else if (itemchance == 323) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  地狱龙!");
			cm.gainItem(1902025 , 1);
			}
			else if (itemchance == 324) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  海贼王!");
			cm.gainItem(1902026 , 1);
			}
			else if (itemchance == 325) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  一刀两断!");
			cm.gainItem(1302056 , 1);
			}
			else if (itemchance == 326) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  狂龙闪电剑!");
			cm.gainItem(1302059 , 1);
			}
			else if (itemchance == 327) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  附魂剑!");
			cm.gainItem(1302107 , 1);
			}
			else if (itemchance == 328) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  烛影摇虹!");
			cm.gainItem(1312030 , 1);
			}
			else if (itemchance == 329) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  狂龙怒斩!");
			cm.gainItem(1312031 , 1);
			}
			else if (itemchance == 330) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  震雷釘!");
			cm.gainItem(1322045 , 1);
			}
			else if (itemchance == 331) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  狂龙地锤 !");
			cm.gainItem(1322052, 1);
			}
			else if (itemchance == 332) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  小鸭游泳圈!");
			cm.gainItem(1322064 , 1);
			}
			else if (itemchance == 333) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  禅翼龙牙破!");
			cm.gainItem(1332049  , 1);
			}
			else if (itemchance == 334) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  半月龙鳞裂!");
			cm.gainItem(1332050  , 1);
			}
			else if (itemchance == 335) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黄金双牙勾!");
			cm.gainItem(1332051  , 1);
			}
			else if (itemchance == 336) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  阴风碎魂刃!");
			cm.gainItem(1332052 , 1);
			}
			else if (itemchance == 337) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  噬魂法杖!");
			cm.gainItem(1372010  , 1);
			}
			else if (itemchance == 338) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  徐太君龙杖!");
			cm.gainItem(1372032 , 1);
			}
			else if (itemchance == 339) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黑精灵王杖!");
			cm.gainItem(1382036  , 1);
			}
			else if (itemchance == 340) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  火灵珠之杖 !");
			cm.gainItem(1382045, 1);
			}
			else if (itemchance == 341) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  毒灵珠之杖!");
			cm.gainItem(1382046  , 1);
			}
			else if (itemchance == 342) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  冰灵珠之杖!");
			cm.gainItem(1382046  , 1);
			}
			else if (itemchance == 343) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  雷灵珠之杖!");
			cm.gainItem(1382048  , 1);
			}
			else if (itemchance == 344) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  暗焰红电弧杖!");
			cm.gainItem(1382060  , 1);
			}
			else if (itemchance == 345) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  斩天刀!");
			cm.gainItem(1402035  , 1);
			}
			else if (itemchance == 346) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  飞龙巨剑!");
			cm.gainItem(1402036  , 1);
			}
			else if (itemchance == 347) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙背刃!");
			cm.gainItem(1072348, 1);
			}
			else if (itemchance == 348) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  樱花伞!");
			cm.gainItem(1402063 , 1);
			}
			else if (itemchance == 349) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  龙魂斧!");
			cm.gainItem(1412021 , 1);
			}
			else if (itemchance == 350) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  炼狱魔龙斧 !");
			cm.gainItem(1412026  , 1);
			}
			else if (itemchance == 351) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  粉红海豹抱枕!");
			cm.gainItem(1422030 , 1);
			}
			else if (itemchance == 352) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  蓝色海豹抱枕!");
			cm.gainItem(1422031 , 1);
			}
			else if (itemchance == 353) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  红莲落神枪 !");
			cm.gainItem(1432030 , 1);
			}
			else if (itemchance == 354) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得极其绝世  盘龙七冲枪!");
			cm.gainItem(1432038 , 1);
			}
			else if (itemchance == 355) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  月灵戟!");
			cm.gainItem(1442002 , 1);
			}
			else if (itemchance == 356) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  战魂斗杀戟!");
			cm.gainItem(1442044 , 1);
			}
			else if (itemchance == 357) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  暗焰红电弧戟!");
			cm.gainItem(1442068  , 1);
			}
			else if (itemchance == 358) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  死神斧!");
			cm.gainItem(1442078 , 1);
			}
			else if (itemchance == 359) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  天鹰弓!");
			cm.gainItem(1452019 , 1);
			}
			else if (itemchance == 360) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  金龙振翅弓!");
			cm.gainItem(1452044, 1);
			}
			else if (itemchance == 361) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  暗焰红电弧弓!");
			cm.gainItem(1452060 , 1);
			}
			else if (itemchance == 362) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  光圣鹅弩!");
			cm.gainItem(1462015 , 1);
			}
			else if (itemchance == 363) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  黄色飞龙弩!");
			cm.gainItem(1462039 , 1);
			}
			else if (itemchance == 364) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  寒木升龙拳!");
			cm.gainItem(1472051 , 1);
			}
			else if (itemchance == 365) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  碧水落龙拳!");
			cm.gainItem(1472052 , 1);
			}
			else if (itemchance == 366) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  逆龙咆哮拳!");
			cm.gainItem(1472053 , 1);
			}
			else if (itemchance == 367) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得绝世  剑龙拳甲!");
			cm.gainItem(1482012 , 1);
			}
			else if (itemchance == 368) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒玉佩!");
			cm.gainItem(1122012 , 1);
			}
			else if (itemchance == 369) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒不灭披风 !");
			cm.gainItem(1002776  , 1);
			}
			else if (itemchance == 370) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒冠军盔 !");
			cm.gainItem(1002776  , 1);
			}
			else if (itemchance == 371) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒演武铠 !");
			cm.gainItem(1052155 , 1);
			}
			else if (itemchance == 372) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒坚壁靴 !");
			cm.gainItem(1072355   , 1);
			}
			else if (itemchance == 373) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒定边手套 !");
			cm.gainItem(1082234   , 1);
			}
			else if (itemchance == 374) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒寒冰盾 !");
			cm.gainItem(1092058   , 1);
			}
			else if (itemchance == 375) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒破甲剑 !");
			cm.gainItem(1302081 , 1);
			}
			else if (itemchance == 376) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒断蚺斧 !");
			cm.gainItem(1312037  , 1);
			}
			else if (itemchance == 377) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒惊破天 !");
			cm.gainItem(1322060   , 1);
			}
			else if (itemchance == 378) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒玄冥剑 !");
			cm.gainItem(1402046  , 1);
			}
			else if (itemchance == 379) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒碎鼋斧 !");
			cm.gainItem(1412033 , 1);
			}
			else if (itemchance == 380) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒威震天 !");
			cm.gainItem(1422037  , 1);
			}
			else if (itemchance == 381) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒显圣枪 !");
			cm.gainItem(1432047  , 1);
			}
			else if (itemchance == 382) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒神光戟 !");
			cm.gainItem(1442063  , 1);
			}
			else if (itemchance == 383) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒玄妙帽 !");
			cm.gainItem(1002777  , 1);
			}
			else if (itemchance == 384) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒奥神袍 !");
			cm.gainItem(1052156  , 1);
			}
			else if (itemchance == 385) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒缥缈鞋 !");
			cm.gainItem(1072356  , 1);
			}
			else if (itemchance == 386) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒逍遥手套 !");
			cm.gainItem(1082235  , 1);
			}
			else if (itemchance == 387) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒魔光盾 !");
			cm.gainItem(1092057  , 1);
			}
			else if (itemchance == 388) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒蝶翼杖 !");
			cm.gainItem(1372044  , 1);
			}
			else if (itemchance == 389) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒冰轮杖 !");
			cm.gainItem(1382057  , 1);
			}
			else if (itemchance == 390) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒霓翎帽 !");
			cm.gainItem(1002778    , 1);
			}
			else if (itemchance == 391) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒巡礼者 !");
			cm.gainItem(1052157  , 1);
			}
			else if (itemchance == 392) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒彩虹鞋 !");
			cm.gainItem(1072357  , 1);
			}
			else if (itemchance == 393) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒白云手套 !");
			cm.gainItem(1082236  , 1);
			}
			else if (itemchance == 394) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒惊电弓 !");
			cm.gainItem(1452057  , 1);
			}
			else if (itemchance == 395) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒冥雷弩 !");
			cm.gainItem(1462050  , 1);
			}
			else if (itemchance == 396) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒迷踪帽 !");
			cm.gainItem(1002779  , 1);
			}
			else if (itemchance == 397) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒翻云服 !");
			cm.gainItem(1052158  , 1);
			}
			else if (itemchance == 398) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒舞空靴 !");
			cm.gainItem(1072358  , 1);
			}
			else if (itemchance == 399) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的永恒探云手套 !");
			cm.gainItem(1082237 , 1);
			}
			else if (itemchance == 401) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的龙背刃!");
			cm.gainItem(1402037, 1);
			}
			else if (itemchance == 402) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的倚天屠龙记剑!");
			cm.gainItem(1402061, 1);
			}
			else if (itemchance >= 403) { 
cm.serverNotice("『高级百宝箱』：恭喜"+ cm.getChar().getName() +"，获得传说中的  高级百宝券N张!!!");
			cm.gainItem(5220010, itemamount);
			}





                        cm.dispose();
		}
	}
}
