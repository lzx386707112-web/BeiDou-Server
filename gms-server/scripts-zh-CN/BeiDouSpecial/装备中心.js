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
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[装备中心]#k系统#n\t\t\t\t\r\n";
var status = -1;

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
        text += " \r\n";
        text += "#L3#精灵吊坠每日强化#l\t\r\n\r\n";
        text += "#L1#装备洗练#l\t\r\n\r\n";
        text += "#L0#时装属性转移#l\t\r\n\r\n";
        text += "#L2#装备制作#l\t\r\n\r\n";
        text += "#L4#星级强化#l\t\r\n\r\n";
        text += "#L5#装备分解#l\t\r\n\r\n";
        text += "#L7#魔方洗练#l\t\r\n\r\n";
        // text += "#L6#老的装备制作#l\t\r\n\r\n";
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
            openNpc("时装属性转移");
            break;
        case 1:
            openNpc("装备洗练");
            break;
        case 2:
            openNpc("装备制作/装备制作");
            break;
        case 3:
            openNpc("每日装备强化");
            break;
        case 4:
            openNpc("装备制作/星级强化");
            break;
        case 5:
            openNpc("装备分解");
            break;
        case 6:
            openNpc("装备制作/装备制作old");
            break;
        case 7:
            openNpc("魔方洗练");
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
