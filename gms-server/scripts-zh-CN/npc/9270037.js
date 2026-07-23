/* 	Jimmy
	Singapore Random Hair/Color Changer
	@Author Cody (FlowsionMS)
        @Author AAron (FlowsionMS)

        GMS-like revised by Ronan -- contents found thanks to Mitsune (GamerBewbs), Waltzing, AyumiLove
*/

var status = 0;
var beauty = 0;
var mhair_r = Array(30110, 30180, 30260, 30290, 30300, 30350, 30470, 30720, 30840);
var fhair_r = Array(31110, 31200, 31250, 31280, 31600, 31640, 31670, 31810, 34010);
var hairnew = Array();

function pushIfItemExists(array, itemid) {
    if ((itemid = cm.getCosmeticItem(itemid)) != -1 && !cm.isCosmeticEquipped(itemid)) {
        array.push(itemid);
    }
}

function start() {
	status = -1;
	action(1, 0, 0);
}

function action(mode, type, selection) {
	if (mode < 1) {  // disposing issue with stylishs found thanks to Vcoc
                if (type == 7) {
                        cm.sendNext("我想你还没有准备好做出改变。什么时候准备好了请告诉我!");
                }
                
		cm.dispose();
	} else {
		if (mode == 1)
			status++;
		else
			status--;
		if (status == 0) {
			cm.sendSimple("嗨，我是这里的助理。别担心，我已经足够优秀了。如果你有 #b#t5150032##k 或 #b#t5151027##k 不管怎样，请允许我来帮你做头发？\r\n#L0#理发: #i5150032##t5150032##l\r\n#L1#染发: #i5151027##t5151027##l");
		} else if (status == 1) {
			if (selection == 0) {
				beauty = 1;
				hairnew = Array();
				if (cm.getChar().getGender() == 0) {
					for(var i = 0; i < mhair_r.length; i++) {
						pushIfItemExists(hairnew, mhair_r[i] + parseInt(cm.getChar().getHair()
 % 10));
					}
				} 
				if (cm.getChar().getGender() == 1) {
					for(var i = 0; i < fhair_r.length; i++) {
						pushIfItemExists(hairnew, fhair_r[i] + parseInt(cm.getChar().getHair()
 % 10));
					}
				}
				cm.sendYesNo("如果您使用普通会员卡，您的发型将随机更改为新造型。您还有机会获得高级会员卡无法得到的新发型。你想使用#b#t5150032##k来打造迷人的新造型吗?");
			} else if (selection == 1) {
				beauty = 2;
				haircolor = Array();
				var current = parseInt(cm.getChar().getHair()
/10)*10;
				for(var i = 0; i < 8; i++) {
					pushIfItemExists(haircolor, current + i);
				}
				cm.sendYesNo("如果您使用普通会员卡，您的头发颜色将随机更改为新颜色。您确定要使用#b#t5151027##k来随机更改头发颜色吗？");
			}
		}
		else if (status == 2){
			cm.dispose();
			if (beauty == 1){
				if (cm.haveItem(5150032) == true){
					cm.gainItem(5150032, -1);
					cm.setHair(hairnew[Math.floor(Math.random() * hairnew.length)]);
					cm.sendOk("享受你的新发型吧!");
				} else {
					cm.sendNext("你需要会员卡我才能更换你的发型。你没有忘记，对吧?");
				}
			}
			if (beauty == 2){
				if (cm.haveItem(5151027) == true){
					cm.gainItem(5151027, -1);
					cm.setHair(haircolor[Math.floor(Math.random() * haircolor.length)]);
					cm.sendOk("享受你的新发色吧!");
				} else {
					cm.sendNext("你需要会员卡我才能更换你的发色。你没有忘记，对吧？");
				}
			}
		}
	}
}