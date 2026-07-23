/*
	This file is part of the OdinMS Maple Story Server
    Copyright (C) 2008 Patrick Huy <patrick.huy@frz.cc>
		       Matthias Butz <matze@odinms.de>
		       Jan Christian Meyer <vimes@odinms.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation version 3 as published by
    the Free Software Foundation. You may not use, modify or distribute
    this program under any other version of the GNU Affero General Public
    License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
/* 	
	NPC Name: 		Big Headward
        Map(s): 		Victoria Road : Henesys Hair Salon (100000104)
	Description: 		Random haircut

        GMS-like revised by Ronan. Contents found thanks to Mitsune (GamerBewbs), Waltzing, AyumiLove
*/

var status = 0;

var mhair_r = Array(35000, 35090, 35210, 38380, 35060, 35100, 35150, 35200, 35260, 35260, 35330, 35350, 35290, 35300, 35420, 35440, 35310, 35330, 35360, 35430, 35440, 35460, 35470, 35510, 35550, 35560, 35600, 35660, 36690, 36710, 36750, 36760, 36810, 36820, 36920, 36340, 36030, 33810, 33980, 33670, 33580, 33320, 36000, 36420, 36460, 36470, 36480, 36510, 36520, 36530, 36560, 36580, 36590, 36640, 36680, 36700, 33550, 33820, 33380, 33930, 32120, 33150, 33310, 33600, 33640, 36310, 33750, 33250, 33350, 33440, 35050, 35170, 35180, 33290, 33030, 36300, 33780, 33700, 33390, 33260, 33340, 33240, 33120, 33000, 35070, 36280, 33750, 36310, 36220, 36180, 36330, 36120, 36530, 36770, 33800, 33740, 33690, 33630, 33180, 34440, 33280, 33300, 33220, 36350, 33830, 36010, 36020, 35020, 32470, 35140, 35160, 36560, 36380, 32440);

var fhair_r = Array(37980, 37860, 37820, 37670, 37640, 37300, 37260, 37140, 37030, 34670, 38030, 38050, 38060, 38250, 38250, 38310, 37310, 35080, 35100, 34980, 35190, 35210, 38380, 38390, 38470, 38470, 38490, 38310, 38270, 38130, 38400, 38410, 38420, 38430, 38450, 38520, 38540, 38600, 38610, 38440, 38460, 38490, 38520, 38560, 38570, 38580, 38590, 38620, 36640, 38650, 38680, 38690, 38700, 38760, 31610, 31560, 31230, 37640, 37690, 36980, 38070, 37990, 37960, 37930, 37920, 34450, 37950, 37810, 37190, 37060, 37000, 34970, 34890, 34860, 34810, 34770, 34750, 34670, 34600, 33970, 34450, 33140, 37440, 37450, 37490, 37560, 34160, 34300, 34260, 34240, 34210, 38290, 38130, 38100, 38020, 38010, 38120, 37330, 37340, 34070, 37710, 34870, 34800, 34760, 37700, 37320, 34330, 34840, 34850, 34830, 34110, 34510, 34250, 34270, 37400, 37370, 37380, 37350, 37530, 37520, 36700);

var mhair_v = Array(35000, 35090, 35210, 38380, 35060, 35100, 35150, 35200, 35260, 35260, 35330, 35350, 35290, 35300, 35420, 35440, 35310, 35330, 35360, 35430, 35440, 35460, 35470, 35510, 35550, 35560, 35600, 35660, 36690, 36710, 36750, 36760, 36810, 36820, 36920, 36340, 36030, 33810, 33980, 33670, 33580, 33320, 36000, 36420, 36460, 36470, 36480, 36510, 36520, 36530, 36560, 36580, 36590, 36640, 36680, 36700, 33550, 33820, 33380, 33930, 32120, 33150, 33310, 33600, 33640, 36310, 33750, 33250, 33350, 33440, 35050, 35170, 35180, 33290, 33030, 36300, 33780, 33700, 33390, 33260, 33340, 33240, 33120, 33000, 35070, 36280, 33750, 36310, 36220, 36180, 36330, 36120, 36530, 36770, 33800, 33740, 33690, 33630, 33180, 34440, 33280, 33300, 33220, 36350, 33830, 36010, 36020, 35020, 32470, 35140, 35160, 36560, 36380, 32440);

var fhair_v = Array(37980, 37860, 37820, 37670, 37640, 37300, 37260, 37140, 37030, 34670, 38030, 38050, 38060, 38250, 38250, 38310, 37310, 35080, 35100, 34980, 35190, 35210, 38380, 38390, 38470, 38470, 38490, 38310, 38270, 38130, 38400, 38410, 38420, 38430, 38450, 38520, 38540, 38600, 38610, 38440, 38460, 38490, 38520, 38560, 38570, 38580, 38590, 38620, 36640, 38650, 38680, 38690, 38700, 38760, 31610, 31560, 31230, 37640, 37690, 36980, 38070, 37990, 37960, 37930, 37920, 34450, 37950, 37810, 37190, 37060, 37000, 34970, 34890, 34860, 34810, 34770, 34750, 34670, 34600, 33970, 34450, 33140, 37440, 37450, 37490, 37560, 34160, 34300, 34260, 34240, 34210, 38290, 38130, 38100, 38020, 38010, 38120, 37330, 37340, 34070, 37710, 34870, 34800, 34760, 37700, 37320, 34330, 34840, 34850, 34830, 34110, 34510, 34250, 34270, 37400, 37370, 37380, 37350, 37530, 37520, 36700);

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
        cm.dispose();
    } else {
        if (mode == 1)
            status++;
        else
            status--;
        
        if (status == 0) {
            cm.sendSimple("#p1012117#是世界上最迷人、最时尚的造型师。如果你想找最好看的发型，就别再找别人了!\r\n\#L0##i5150040# #t5150040#  随机发型#l\r\n\#L1##i5150044# #t5150044#  自选发型#l");
        } else if (status == 1) {
            if (selection == 0) {
                beauty = 1;
                cm.sendYesNo("如果你使用这个普通会员卡，你的头发可能会变成一个随机的新外观。你还想用#b#t5150040##k做头发吗？我无论如何都会为你做的。但别忘了，结果随机的！");
            } else {
                beauty = 2;
                
                hairnew = Array();
                if (cm.getPlayer().getGender() == 0) {
                    for(var i = 0; i < mhair_v.length; i++) {
                        pushIfItemExists(hairnew, mhair_v[i] + parseInt(cm.getPlayer().getHair() % 10));
                    }
                }
                else {
                    for(var i = 0; i < fhair_v.length; i++) {
                        pushIfItemExists(hairnew, fhair_v[i] + parseInt(cm.getPlayer().getHair() % 10));
                    }
                }
                
                cm.sendStyle("使用高级会员卡，你可以选择你的发型。请选择最能给你带来快乐的款式。", hairnew);
            }
        } else if (status == 2) {
            if (beauty == 1) {
                if (cm.haveItem(5150040) == true){
                    hairnew = Array();
                    if (cm.getPlayer().getGender() == 0) {
                        for(var i = 0; i < mhair_r.length; i++) {
                            pushIfItemExists(hairnew, mhair_r[i] + parseInt(cm.getPlayer().getHair() % 10));
                        }
                    }
                    else {
                        for(var i = 0; i < fhair_r.length; i++) {
                            pushIfItemExists(hairnew, fhair_r[i] + parseInt(cm.getPlayer().getHair() % 10));
                        }
                    }

                    cm.gainItem(5150040, -1);
                    cm.setHair(hairnew[Math.floor(Math.random() * hairnew.length)]);
                    cm.sendOk("享受你的新发型吧!");
                } else {
                    cm.sendOk("嗯…看起来你没有我们指定的会员卡。。。没有它恐怕我不能给你理发。对不起。。。");
                }
            } else if (beauty == 2) {
                if (cm.haveItem(5150044) == true){
                    cm.gainItem(5150044, -1);
                    cm.setHair(hairnew[selection]);
                    cm.sendOk("享受你的新发型吧!");
                } else {
                    cm.sendOk("嗯…看起来你没有我们指定的会员卡。。。没有它恐怕我不能给你理发。对不起。。。");
                }
            }
            
            cm.dispose();
        }
    }
}
