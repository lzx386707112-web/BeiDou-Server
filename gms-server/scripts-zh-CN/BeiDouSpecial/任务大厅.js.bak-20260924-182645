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

/**
 * @description 拍卖行中心脚本
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[任务大厅]#k系统#n\t\t\t\t\r\n";
var status = -1;
var i = 0;

function start() {
    action(1, 0, 0)
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else if (mode === -1) {
        status--;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        let text = OldTitle;
        text += "#b \r\n";
        text += "#L0#每日任务#l\t\t\t";
        text += "#L1#主线任务#l\t\t\t";
        text += "#L2#血衣合成#l\t\r\n\r\n";
        text += "#L3#怪物卡戒#l\t\t\t";
        text += "#L4#世界任务#l\t\t\t";
        text += "#L5#跑环#l\t\r\n\r\n";
        text += "#L6#狩猎#l\t\t\t";
        text += "#L7#Boss成长#l\t\r\n\r\n";
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        case 0:
            openNpc("任务/每日任务");
            break;
        case 1:
            openNpc("任务/主线任务");
            break;
        case 2:
            openNpc("任务/血衣合成");  //明珠港怪物卡戒指NPC
            break;
        case 3:
            openNpc("2006");
            break;
        case 4:
            openNpc("任务/世界任务");
            break;
        case 5:
            openNpc("任务/跑环");
            break;
        case 6:
            openNpc("任务/狩猎");
            break;
        case 7:
            openNpc("Boss成长系统");
            break;
        default:
            cm.sendOk("该功能暂不支持，敬请期待！");
            cm.dispose();
    }
}

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}
