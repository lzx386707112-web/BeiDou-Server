//Gachaphon

importPackage(net.sf.odinms.client);



var status = 0;
var chance1 = Math.floor(Math.random()*200+1);
var chance2 = Math.floor(Math.random()*50);
var chance3 = (Math.floor(Math.random()*20)+1);
var chance4 = Math.floor(Math.random()*2+1);
var itemchance = chance1 + chance2 + chance3 * chance4;
var itemamount = Math.floor(Math.random()*50+1);


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
				cm.sendNext("我是快乐百宝箱.\r\n如果你有#r快乐百宝券#b#v5220000##k\r\n可以在我这里随机换取物品哦!\r\n如果抽到高级快乐百宝券，你可以到我头上的#r高级快乐百宝箱#k抽奖哦！！");
			}
		else if (status == 1) {
                        if (cm.haveItem(5220000)) {
			cm.sendYesNo("我看见你有换取道具了,你要使用它?");
			}
			else if (!cm.haveItem(5220000)) {
			cm.sendOk("你身上没有兑换道具，#b魂#k交代我不能帮你!.");
			cm.dispose();
			}
		}
		else if (status == 2) {
			cm.gainItem(5220000, -1);

			if ((itemchance >= 1) && (itemchance <= 20)) {
			cm.gainItem(2000004, itemamount);
			}
			else if ((itemchance >= 21) && (itemchance <= 40)) {
			cm.gainItem(2020012, itemamount);
			}
			else if ((itemchance >= 41) && (itemchance <= 50)) {
			cm.gainItem(2000005, itemamount);
			}
			else if ((itemchance >= 51) && (itemchance <= 60)) {
			cm.gainItem(5110000, itemamount);
			}
			else if ((itemchance >= 61) && (itemchance <= 70)) {
			cm.gainItem(2022027, itemamount);
			}
			else if (itemchance == 71) {
			cm.gainItem(4000234, 10);
			}
                        else if (itemchance == 72) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得温度计!");
			cm.gainItem(1402014, 1);
			}
			else if (itemchance == 73) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得南瓜灯笼!");
			cm.gainItem(1402044, 1);
			}
			else if (itemchance == 75) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得酒瓶!");
			cm.gainItem(1422011, 1);
			}
			else if (itemchance == 76) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得燃烧的火焰刀!");
			cm.gainItem(1302063, 1);
			}
			else if (itemchance == 77) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得七夕!");
			cm.gainItem(1322051, 1);
			}
			else if (itemchance == 78) {
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得乌龙茶!");
			cm.gainItem(1332021, 1);
			}
			else if (itemchance == 79) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得领路灯!");
			cm.gainItem(372017, 1);
			}	
			else if (itemchance == 80) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得钓鱼秆!");
			cm.gainItem(1432039, 1);
			}	
			else if (itemchance == 81) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得冻冻鱼!");
			cm.gainItem(1442039, 1);
			}
			else if (itemchance == 82) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName(勇气耳环) +"，获得!");
			cm.gainItem(1032030, 1);
			}
			else if (itemchance == 83) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得绿色蝶形领结!");
			cm.gainItem(1122001, 1);
			}	
			else if (itemchance == 84) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得红色蝶形领结!");
			cm.gainItem(1122002, 1);
			}
			else if (itemchance == 85) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得黄色蝶形领结!");
			cm.gainItem(1122003, 1);
			}
			else if (itemchance == 86) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得蓝色蝶形领结!");
			cm.gainItem(1122006, 1);
			}
			else if (itemchance == 87) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得熔岩披风!");
			cm.gainItem(1102148, 1);
			}	
			else if (itemchance == 88) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得冰凌披风!");
			cm.gainItem(1102149, 1);
			}
			else if (itemchance == 89) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得浴巾!");
			cm.gainItem(1050127, 1);
			}
			else if (itemchance == 90) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得红浴巾!");
			cm.gainItem(1051098, 1);
			}
			else if (itemchance == 91) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得蓝浴巾!");
			cm.gainItem(1050100, 1);
			}
			else if (itemchance == 92) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得香菇!");
			cm.gainItem(1382016, 1);
			}
			else if (itemchance == 93) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得冻冻鱼!");
			cm.gainItem(1442039, 1);
			}
			else if (itemchance == 94) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得!工地手套(蓝)");
			cm.gainItem(1082147, 1);
			}
			else if (itemchance == 95) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得工地手套(紫)!");
			cm.gainItem(1082148, 1);
			}
			else if (itemchance == 96) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得工地手套(灰)!");
			cm.gainItem(1082150, 1);
			}
			else if (itemchance == 97) {
cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得传说中的高级百宝券!");
			cm.gainItem(5220010, 1);
			}
			else if (itemchance == 98) {
			cm.gainItem(1102041, 1);
			}
			else if (itemchance == 99) {
			cm.gainItem(1102042, 1);
			}
			else if (itemchance == 100) {

			cm.gainItem(1322024, 1);
			}
			else if (itemchance == 101) {
			cm.gainItem(1082148, 1);
			}
			else if (itemchance == 102) {
			cm.gainItem(1002012, 1);
			}
			else if (itemchance == 103) {
			cm.gainItem(1322012, 1);
			}
			else if (itemchance == 104) {
			cm.gainItem(1322022, 1);
			}
			else if (itemchance == 105) {
			cm.gainItem(1002020, 1);
			}
			else if (itemchance == 106) {
			cm.gainItem(1302013, 1);
			}
			else if (itemchance == 107) {
			cm.gainItem(1082146, 1);
			}
			else if (itemchance == 108) {
			cm.gainItem(1442014, 1);
			}
			else if (itemchance == 109) {
			cm.gainItem(1002096, 1);
			}
			else if (itemchance == 110) {
			cm.gainItem(1302017, 1);
			}
			else if (itemchance == 111) {
			cm.gainItem(1442012, 1);
			}
			else if (itemchance == 112) {
			cm.gainItem(1322010, 1);
			}
			else if (itemchance == 113) {
			cm.gainItem(1442011, 1);
			}
			else if (itemchance == 114) {
			cm.gainItem(1442018, 1);
			}
			else if (itemchance == 115) {
			cm.gainItem(1092011, 1);
			}
			else if (itemchance == 116) {
			cm.gainItem(1092014, 1);
			}
			else if (itemchance == 117) {
			cm.gainItem(1302003, 1);
			}
			else if (itemchance == 118) {
			cm.gainItem(1432001, 1);
			}
			else if (itemchance == 119) {
			cm.gainItem(1312011, 1);
			}
			else if (itemchance == 120) {
			cm.gainItem(1002088, 1);
			}
			else if (itemchance == 121) {
			cm.gainItem(1041020, 1);
			}
			else if (itemchance == 122) {
			cm.gainItem(1322015, 1);
			}
			else if (itemchance == 123) {
			cm.gainItem(1442004, 1);
			}
			else if (itemchance == 124) {
			cm.gainItem(1422008, 1);
			}
			else if (itemchance == 125) {
			cm.gainItem(1302056, 1);
			}
			else if (itemchance == 126) {
			cm.gainItem(1432000, 1);
			}
			else if (itemchance == 127) {
			cm.gainItem(1382001, 1);
			}
			else if (itemchance == 128) {
			cm.gainItem(1041053, 1);
			}
			else if (itemchance == 129) {
			cm.gainItem(1060014, 1);
			}
			else if (itemchance == 130) {
			cm.gainItem(1050053, 1);
			}
			else if (itemchance == 131) {
			cm.gainItem(1051032, 1);
			}
			else if (itemchance == 132) {
			cm.gainItem(1050073, 1);
			}
			else if (itemchance == 133) {
			cm.gainItem(1061036, 1);
			}
			else if (itemchance == 134) {
			cm.gainItem(1002253, 1);
			}
			else if (itemchance == 135) {
			cm.gainItem(1002034, 1);
			}
			else if (itemchance == 136) {
			cm.gainItem(1051025, 1);
			}
			else if (itemchance == 137) {
			cm.gainItem(1050067, 1);
			}
			else if (itemchance == 138) {
			cm.gainItem(1051052, 1);
			}
			else if (itemchance == 139) {
			cm.gainItem(1002072, 1);
			}
			else if (itemchance == 140) {
			cm.gainItem(1002144, 1);
			}
			else if (itemchance == 141) { 
			cm.gainItem(1051054, 1);
			}
			else if (itemchance == 142) { 
			cm.gainItem(1050069, 1);
			}
			else if (itemchance == 143) { 
			cm.gainItem(1372007, 1);
			}
			else if (itemchance == 144) { 
			cm.gainItem(1050056, 1);
			}
			else if (itemchance == 145) { 
			cm.gainItem(1050074, 1);
			}
			else if (itemchance == 146) { 
			cm.gainItem(1002254, 1);
			}
			else if (itemchance == 147) {
			cm.gainItem(1002274, 1);
			}
			else if (itemchance == 148) { 
			cm.gainItem(1002218, 1);
			}
			else if (itemchance == 149) { 
			cm.gainItem(1051055, 1);
			}
			else if (itemchance == 150) { 
			cm.gainItem(1382010, 1);
			}
			else if (itemchance == 151) { 
			cm.gainItem(1002246, 1);
			}
			else if (itemchance == 152) { 
			cm.gainItem(1050039, 1);
			}
			else if (itemchance == 153) { 
			cm.gainItem(1382007, 1);
			}
			else if (itemchance == 154) { 
			cm.gainItem(1372000, 1);
			}
			else if (itemchance == 155) { 
			cm.gainItem(1002013, 1);
			}
			else if (itemchance == 156) { 
			cm.gainItem(1050072, 1);
			}
			else if (itemchance == 157) { 
			cm.gainItem(1002036, 1);
			}
			else if (itemchance == 158) { 
			cm.gainItem(1002243, 1);
			}
			else if (itemchance == 159) { 
			cm.gainItem(1372008, 1);
			}
			else if (itemchance == 160) { 
			cm.gainItem(1382008, 1);
			}
			else if (itemchance == 161) { 
			cm.gainItem(1382011, 1);
			}
			else if (itemchance == 162) { 
			cm.gainItem(1092021, 1);
			}
			else if (itemchance == 163) { 
			cm.gainItem(1051034, 1);
			}
			else if (itemchance == 164) { 
			cm.gainItem(1050047, 1);
			}

			else if (itemchance == 165) { 
			cm.gainItem(1040019, 1);
			}
			else if (itemchance == 166) { 
			cm.gainItem(1041031, 1);
			}
			else if (itemchance == 167) { 
			cm.gainItem(1051033, 1);
			}
			else if (itemchance == 168) { 
			cm.gainItem(1002153, 1);
			}
			else if (itemchance == 169) { 
			cm.gainItem(1002252, 1);
			}
			else if (itemchance == 170) { 
			cm.gainItem(1051024, 1);
			}
			else if (itemchance == 171) { 
			cm.gainItem(1002153, 1);
			}
			else if (itemchance == 172) { 
			cm.gainItem(1050068, 1);
			}
			else if (itemchance == 173) { 
			cm.gainItem(1382003, 1);
			}
			else if (itemchance == 174) { 
			cm.gainItem(1382006, 1);
			}
			else if (itemchance == 175) { 
			cm.gainItem(1050055, 1);
			}
			else if (itemchance == 176) { 
			cm.gainItem(1051031, 1);
			}
			else if (itemchance == 177) { 
			cm.gainItem(1050025, 1);
			}
			else if (itemchance == 178) { 
			cm.gainItem(1002155, 1);
			}
			else if (itemchance == 179) { 
			cm.gainItem(1002245, 1);
			}
			else if (itemchance == 180) { 
			cm.gainItem(13720013, 1);
			}
			else if (itemchance == 181) { 
			cm.gainItem(1452004, 1);
			}
			else if (itemchance == 182) { 
			cm.gainItem(1452023, 1);
			}
			else if (itemchance == 183) { 
			cm.gainItem(1060057, 1);
			}
			else if (itemchance == 184) { 
			cm.gainItem(1040071, 1);
			}
			else if (itemchance == 185) { 
			cm.gainItem(1002137, 1);
			}
			else if (itemchance == 186) { 
			cm.gainItem(1462009, 1);
			}
			else if (itemchance == 187) { 
			cm.gainItem(1452017, 1);
			}
			else if (itemchance == 188) { 
			cm.gainItem(1040025, 1);
			}
			else if (itemchance == 189) { 
			cm.gainItem(1041027, 1);
			}
			else if (itemchance == 190) { 
			cm.gainItem(1452005, 1);
			}
			else if (itemchance == 191) { 
			cm.gainItem(1452007, 1);
			}
			else if (itemchance == 192) { 
			cm.gainItem(1061057, 1);
			}
			else if (itemchance == 193) { 
			cm.gainItem(1472006, 1);
			}
			else if (itemchance == 194) { 
			cm.gainItem(1472019, 1);
			}
			else if (itemchance == 195) { 
			cm.gainItem(1060084, 1);
			}
			else if (itemchance == 196) { 
			cm.gainItem(1472028, 1);
			}
			else if (itemchance == 197) { 
			cm.gainItem(1002179, 1);
			}
			else if (itemchance == 198) { 
			cm.gainItem(1082074, 1);
			}
			else if (itemchance == 199) { 
			cm.gainItem(1332015, 1);
			}
			else if (itemchance == 200) { 
			cm.gainItem(1432001, 1);
			}
			else if (itemchance == 201) { 
			cm.gainItem(1060071, 1);
			}
			else if (itemchance == 202) { 
			cm.gainItem(1472007, 1);
			}
			else if (itemchance == 203) { 
			cm.gainItem(1472002, 1);
			}
			else if (itemchance == 204) { 
			cm.gainItem(1051009, 1);
			}
			else if (itemchance == 205) { 
			cm.gainItem(1061037, 1);
			}
			else if (itemchance == 206) { 
			cm.gainItem(1332016, 1);
			}
			else if (itemchance == 207) { 
			cm.gainItem(1332034, 1);
			}
			else if (itemchance == 208) { 
			cm.gainItem(1472020, 1);
			}
			else if (itemchance == 209) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2048009, 1);
			}
			else if (itemchance == 210) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2048007, 1);
			}
			else if (itemchance == 211) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044707, 1);
			}
			else if (itemchance == 212) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044607, 1);
			}
			else if (itemchance == 213) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044507, 1);
			}
			else if (itemchance == 214) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044407, 1);
			}
			else if (itemchance == 215) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044307, 1);
			}
			else if (itemchance == 216) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044207, 1);
			}
			else if (itemchance == 217) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044107, 1);
			}
			else if (itemchance == 218) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044007, 1);
			}
			else if (itemchance == 219) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043807, 1);
			}
			else if (itemchance == 220) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043707, 1);
			}
			else if (itemchance == 221) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043307, 1);
			}
			else if (itemchance == 222) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043207, 1);
			}
			else if (itemchance == 223) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043107, 1);
			}
			else if (itemchance == 224) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043012, 1);
			}
			else if (itemchance == 225) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041057, 1);
			}
			else if (itemchance == 226) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041055, 1);
			}
			else if (itemchance == 227) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041053, 1);
			}
			else if (itemchance == 228) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041049, 1);
			}
			else if (itemchance == 229) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041047, 1);
			}
			else if (itemchance == 230) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041045, 1);
			}
			else if (itemchance == 231) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2041043, 1);
			}
			else if (itemchance == 232) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040911, 1);
			}
			else if (itemchance == 233) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040822, 1);
			}
			else if (itemchance == 234) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040820, 1);
			}
			else if (itemchance == 235) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040723, 1);
			}
			else if (itemchance == 236) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040721, 1);
			}
			else if (itemchance == 237) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040719, 1);
			}
			else if (itemchance == 238) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040315, 1);
			}
			else if (itemchance == 239) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2040912, 1);
			}
			else if (itemchance == 240) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043013, 1);
			}
			else if (itemchance == 241) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043108, 1);
			}
			else if (itemchance == 242) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043208, 1);
			}
			else if (itemchance == 243) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043308, 1);
			}
			else if (itemchance == 244) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043708, 1);
			}
			else if (itemchance == 245) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2043808, 1);
			}
			else if (itemchance == 246) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044008, 1);
			}
			else if (itemchance == 247) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044108, 1);
			}
			else if (itemchance == 248) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044208, 1);
			}
			else if (itemchance == 249) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044308, 1);
			}
			else if (itemchance == 250) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044408, 1);
			}
			else if (itemchance == 251) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044508, 1);
			}
			else if (itemchance == 252) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044608, 1);
			}
			else if (itemchance == 253) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044708, 1);
			}
			else if (itemchance == 254) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044810, 1);
			}
			else if (itemchance == 255) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得神卷一张!");
			cm.gainItem(2044905, 1);
			}			
			else if ((itemchance >= 256) && (itemchance <= 265)) {  
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得工地手套（褐）!");
			cm.gainItem(1082149, 1);
			}
			else if (itemchance == 266) {  
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得紫色盖亚披风!");
			cm.gainItem(1102086, 1);
			}
			else if (itemchance == 267) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得浪人披风（紫）!");
			cm.gainItem(1102042, 1);
			}
			else if (itemchance == 268) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得黄水晶耳环!");
			cm.gainItem(1032026, 1);
			}
			else if (itemchance == 269) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 拉风摩托!");
			cm.gainItem(1902022, 1);
			}
			else if (itemchance == 270) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 最强工作人员鞋!");
			cm.gainItem(1072368, 1);
			}
			else if (itemchance == 271) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 王盾!");
			cm.gainItem(1092048, 1);
			}
			else if (itemchance == 272) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 品克缤套服!");
			cm.gainItem(1052202, 1);
			}
			else if (itemchance == 273) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 莫扎特的寿衣!");
			cm.gainItem(1102194, 1);
			}
			else if (itemchance == 274) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 暴力熊头盔!");
			cm.gainItem(1002905, 1);
			}
			else if (itemchance == 275) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 何露斯之眼!");
			cm.gainItem(1122010, 1);
			}
			else if (itemchance == 276) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 小眼镜!");
			cm.gainItem(1022088, 1);
			}
			else if (itemchance == 277) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 玄冰杖!");
			cm.gainItem(1702211, 1);
			}
			else if (itemchance == 278) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 蓝星跑鞋!");
			cm.gainItem(1072279, 1);
			}
			else if (itemchance == 279) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 深蓝嘻哈裤!");
			cm.gainItem(1062041, 1);
			}
			else if (itemchance == 280) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 黄浴巾!");
			cm.gainItem(1051193, 1);
			}
			else if (itemchance == 281) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 蓝浴巾!");
			cm.gainItem(1050156, 1);
			}
			else if (itemchance == 282) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 我最IN-T恤!");
			cm.gainItem(1042163, 1);
			}
			else if (itemchance == 283) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 五星红旗!");
			cm.gainItem(5010009, 1);
			}
			else if (itemchance == 284) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 飞行伞!");
			cm.gainItem(1002726, 1);
			}
			else if (itemchance == 285) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得稀有 小鱼戒指!");
			cm.gainItem(1112907, 1);
			}
			else if (itemchance == 286) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得沙漠白兔靠椅!");
			cm.gainItem(3010052, 1);
			}
			else if (itemchance == 287) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得沙漠灰兔靠椅!");
			cm.gainItem(3010051, 1);
			}
			else if (itemchance == 288) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得传说中的混沌卷!");
			cm.gainItem(2049100, 1);
			}
			else if (itemchance >= 289) { 
 cm.serverNotice("『活动公告』：恭喜"+ cm.getChar().getName() +"，获得工地手套（褐）!");
			cm.gainItem(1082149, 1);
			}
			cm.dispose();
		}
	}
}
