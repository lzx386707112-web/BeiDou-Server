/*
	Mady By Coffee
	Powered By XXMS
	Warp NPC
*/

var bossmaps = Array(
										Array(800040410,0,"楓城 天守閣最上階")

										);
var monstermaps = Array(
										Array(800040200,0,"楓城 城堡"), 
										Array(800040201,0,"楓城 城堡走廊"), 
										Array(800040202,0,"楓城 城堡走廊2"), 
										Array(800040203,0,"楓城 城堡走廊3"), 
										Array(800040204,0,"楓城 城堡走廊:客房"), 
										Array(800040205,0,"楓城 城堡走廊:客房2"), 
										Array(800040206,0,"楓城 城堡走廊:武器仓库"), 
										Array(800040207,0,"楓城 城堡走廊:武器仓库2"), 
										Array(800040209,0,"楓城 城堡走廊4"), 
										Array(800040210,0,"楓城 陷阱"), 
										Array(800040211,0,"楓城 城堡走廊5"), 
										Array(800040300,0,"楓城 梦幻之室"),
										Array(800040301,0,"楓城 梦幻之室2"),
										Array(800040302,0,"楓城 梦幻之室3"), 
										Array(800040303,0,"楓城 梦幻之室4"), 
										Array(800040304,0,"楓城 梦幻之室5"), 
										Array(800040305,0,"楓城 梦幻之室6"), 
										Array(800040306,0,"楓城 梦幻之室7"), 
										Array(800040307,0,"楓城 梦幻之室8"), 
										Array(800040308,0,"楓城 梦幻之室9"),
										Array(800040309,0,"楓城 梦幻之室10"), 
										Array(800040310,0,"楓城 梦幻之室11"), 
										Array(800040311,0,"楓城 梦幻之室12"), 
										Array(800040312,0,"楓城 梦幻之室13"), 
										Array(800040313,0,"楓城 梦幻之室14"), 
										Array(800040314,0,"楓城 梦幻之室15"), 
										Array(800040315,0,"楓城 梦幻之室16"), 
										Array(800040400,0,"楓城 城堡室内1"), 
										Array(800040401,0,"楓城 城堡室内2")

										); 
var townmaps = Array(
										Array(910000000,0,"自由市场"), 
										Array(1010000,0,"彩虹村"), 
										Array(60000,0,"南港"), 
										Array(104000000,10000,"明珠港"), 
										Array(100000000,10000,"射手村"), 
										Array(101000000,10000,"魔法密林"), 
										Array(102000000,10000,"勇士部落"), 
										Array(103000000,10000,"废弃都市"), 
										Array(120000000,10000,"诺特勒斯号码头"),
										Array(105040300,10000,"林中之城"), 
										Array(211000000,10000,"冰峰雪域"), 
										Array(680000000,10000,"幸福天堂"), 
										Array(230000000,10000,"水下世界"),  
										Array(800040000,10000,"枫城"),  
										Array(221000000,10000,"地球防御本部"), 
										Array(251000000,10000,"百草堂"),
										Array(222000000,10000,"童话村"), 
										Array(270000100,10000,"时间神殿"), 
										Array(250000000,10000,"武陵"), 
										Array(800000000,10000,"古代神社"), 
										Array(801000000,10000,"昭和村"), 
										Array(610010004,10000,"亡灵峡谷"), 
										Array(540010000,10000,"樟宜机场"),
										Array(200000000,10000,"天空之城"),
										Array(220000000,10000,"玩具城"),
										Array(270050300,10000,"黄昏与黎明之间"),
										Array(701000000,10000,"东方神州"),
										Array(930000000,10000,"毒雾森林"),
										Array(930000010,10000,"森林入口")

							);
var chosenMap = -1;
var monsters = 0;
var towns = 0;
var bosses = 0;

importPackage(net.sf.odinms.client);

function start() {
	status = -1;
	action(1, 0, 0);
}

function action(mode, type, selection) {
            if (mode == -1) {
                cm.dispose();
            }
            else {
                if (status >= 3 && mode == 0) {
			cm.sendOk("下次再见!.");
			cm.dispose();
			return;                    
                }
                if (mode == 1) {
			status++;
		}
		else {
			status--;
		}
               if (status == 0) {
                        cm.sendNext("Hi,枫城老大！你想去枫城的任何一个角落都可以叫我！");                  
                }
               if (status == 1) {
                   cm.sendSimple("#fUI/UIWindow.img/QuestIcon/3/0#\r\n#L0#枫城传送#l\r\n#L1#抱歉,我走错了#l");
               }
               else if (status == 2) {
                   if (selection == 0) {
                       cm.sendSimple("#fUI/UIWindow.img/QuestIcon/3/0#\r\n#L0#城镇地图#l\r\n#L1#枫城地图#l\r\n#L2#枫城BOSS地图#l");
                   }
                   else if (selection == 1) {
                       cm.dispose();
                   }
               }
               else if (status == 3) {
                   if (selection == 0) {
                        var selStr = "选择你想去的城市吧.#b";
			for (var i = 0; i < townmaps.length; i++) {
				selStr += "\r\n#L" + i + "#" + townmaps[i][2] + "";
			}
                        cm.sendSimple(selStr);
                        towns = 1;
                   }
                   if (selection == 1) {
                       var selStr = "选择你的枫城地图吧.#b";
                       for (var i = 0; i < monstermaps.length; i++) {
				selStr += "\r\n#L" + i + "#" + monstermaps[i][2] + "";
                       }
                       cm.sendSimple(selStr);
                       monsters = 1;
                   }
                   if (selection == 2) {
                       var selStr = "选择要前往的枫城 BOSS 地图。#b";
                       for (var i = 0; i < bossmaps.length; i++) {
				selStr += "\r\n#L" + i + "#" + bossmaps[i][2] + "";
                       }
                       cm.sendSimple(selStr);
                       bosses = 1;
                   }
               }
            else if (status == 4) {
                if (towns == 1) {
                cm.sendYesNo("你确定要去 " + townmaps[selection][2] + "? 价格:#r"+townmaps[selection][1]+"#k金币");
		chosenMap = selection;
                towns = 2;
                }
                else if (monsters == 1) {
                cm.sendYesNo("你确定要去 " + monstermaps[selection][2] + "? 价格:#r"+monstermaps[selection][1]+"#k金币");
                chosenMap = selection;
                monsters = 2;
                }
                else if (bosses == 1) {
                cm.sendYesNo("你确定要去 " + bossmaps[selection][2] + "? 价格:#r"+bossmaps[selection][1]+"#k金币");
                chosenMap = selection;
                bosses = 2;
                }
            }
            else if (status == 5) {
                if (towns == 2) {
                	if(cm.getMeso()>=townmaps[chosenMap][1]){
                		cm.warp(townmaps[chosenMap][0], 0);
                		cm.gainMeso(-townmaps[chosenMap][1]);
                	}else{
                		cm.sendOk("你没有足够的金币哦!");
                	}
                    cm.dispose();
                }
                else if (monsters == 2) {
                    if(cm.getMeso()>=monstermaps[chosenMap][1]){
                		cm.warp(monstermaps[chosenMap][0], 0);
                		cm.gainMeso(-monstermaps[chosenMap][1]);
                	}else{
                		cm.sendOk("你没有足够的金币哦!");
                	}
                    cm.dispose();
                }
                else if (bosses == 2) {
                    if(cm.getMeso()>=bossmaps[chosenMap][1]){
                		cm.warp(bossmaps[chosenMap][0], 0);
                		cm.gainMeso(-bossmaps[chosenMap][1]);
                	}else{
                		cm.sendOk("你没有足够的金币哦!");
                	}
                    cm.dispose();
                }
            }
              
            }
}
