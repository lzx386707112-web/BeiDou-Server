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
 * @Name         NimaKIN
 * @Author:      Signalize
 * @Author:      MainlandHero - repurposed to be the style setter in-game for mesos
 * @NPC:         9900000
 * @Purpose:     Hair/Face/Eye Changer
 * @Map:         180000000
 */
var status = 0;
var beauty = 0;
var haircolor = Array();
var skin = [0, 1, 2, 3, 4, 5, 9, 10];
var fhair = [40070, 40080, 42100, 42220, 42230, 42240, 42250, 42260, 42270, 43280, 44430, 44460, 46540, 46550, 47140, 48670, 48680, 48690, 48700, 48710, 48720, 48730, 48740, 48750, 48760, 48770];
var hair = [40070, 40080, 42100, 42220, 42230, 42240, 42250, 42260, 42270, 43280, 44430, 44460, 46540, 46550, 47140, 48670, 48680, 48690, 48700, 48710, 48720, 48730, 48740, 48750, 48760, 48770];
var hairnew = Array();
var face = [20000, 20001, 20002, 20003, 20004, 20005, 20006, 20007, 20008, 20009, 20010, 20011, 20012, 20013, 20014, 20015, 20016, 20017, 20018, 20019, 20020, 20021, 20022, 20023, 20024, 20025, 20026, 20027, 20028, 20029, 20031, 20032];
var fface = [21000, 21001, 21002, 21003, 21004, 21005, 21006, 21007, 21008, 21009, 21010, 21011, 21012, 21013, 21014, 21016, 21017, 21018, 21019, 21020, 21021, 21022, 21023, 21024, 21025, 21026, 21027, 21029, 21030];
var facenew = Array();
var colors = Array();
var price = 1000000;

function pushIfItemExists(array, itemid) {
    if ((itemid = cm.getCosmeticItem(itemid)) != -1 && !cm.isCosmeticEquipped(itemid)) {  // thanks Conrad for noticing NPC crashing the player when trying to display inexistent cosmetics
        array.push(itemid);
    }
}

function start() {
    if (cm.getPlayer().gmLevel() < 1) {
        cm.sendOk("嘿，怎么了？");
        cm.dispose();
        return;
    }

    if (cm.getPlayer().isMale()) {
        cm.sendSimple("嘿，你可以用" + price + "金币改变你的外观。你想要改变什么？\r\n#L0#肤色#l\r\n#L1#男性发型#l\r\n#L2#发色#l\r\n#L3#男性眼睛#l\r\n#L4#眼睛颜色#l");
    } else {
        cm.sendSimple("嘿，你可以用" + price + "金币改变你的外观。你想要改变什么？\r\n#L0#肤色#l\r\n#L5#女性发型#l\r\n#L2#发色#l\r\n#L6#女性眼睛#l\r\n#L4#眼睛颜色#l");
    }
}

function action(mode, type, selection) {
    status++;
    if (mode != 1 || cm.getPlayer().gmLevel() < 1) {
        cm.dispose();
        return;
    }
    if (status == 1) {
        beauty = selection + 1;
        if (cm.getMeso() > price) {
            if (selection == 0) {
                cm.sendStyle("选一个?", skin);
            } else if (selection == 1 || selection == 5) {
                (selection == 1 ? hair : fhair).forEach(i => pushIfItemExists(hairnew, i));
                cm.sendStyle("选一个?", hairnew);
            } else if (selection == 2) {
                var baseHair = parseInt(cm.getPlayer().getHair() / 10) * 10;
                for (var k = 0; k < 8; k++) {
                    pushIfItemExists(haircolor, baseHair + k);
                }
                cm.sendStyle("选一个?", haircolor);
            } else if (selection == 3 || selection == 6) {
                (selection == 3 ? face : fface).forEach(j => pushIfItemExists(facenew, j));
                cm.sendStyle("选一个?", facenew);
            } else if (selection == 4) {
                var baseFace = parseInt(cm.getPlayer().getFace() / 1000) * 1000 + parseInt(cm.getPlayer().getFace() % 100);
                for (var i = 0; i < 9; i++) {
                    pushIfItemExists(colors, baseFace + (i * 100));
                }
                cm.sendStyle("选一个?", colors);
            }
        } else {
            cm.sendNext("你的金币不够。很抱歉，没有" + price + "个冒险币，你将无法改变你的外观！");
            cm.dispose();
        }

    } else if (status == 2) {
        if (beauty == 1) {
            cm.setSkin(skin[selection]);
            cm.gainMeso(-price);
        }
        if (beauty == 2 || beauty == 6) {
            cm.setHair(hairnew[selection]);
            cm.gainMeso(-price);
        }
        if (beauty == 3) {
            cm.setHair(haircolor[selection]);
            cm.gainMeso(-price);
        }
        if (beauty == 4 || beauty == 7) {
            cm.setFace(facenew[selection]);
            cm.gainMeso(-price);
        }
        if (beauty == 5) {
            cm.setFace(colors[selection]);
            cm.gainMeso(-price);
        }
        cm.dispose();
    }
}
