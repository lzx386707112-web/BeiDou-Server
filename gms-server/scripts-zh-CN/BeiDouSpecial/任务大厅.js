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
// ============================================================
// 血衣合成 / 怪物卡戒 / Boss成长 / 跑环 / 狩猎 已移到主菜单 9900001：
//   角色提升 = 血衣合成、怪物卡戒、Boss成长
//   每日日常 = 跑环、狩猎
// 这里只保留 每日任务 / 主线任务 / 世界任务
// ============================================================
// 每格定宽（半角单位）+ 格间隔，一行三格总宽约 36，远小于对话框宽度（约 54）
var 菜单格宽 = 12;
var 菜单格间隔 = 2;

var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[任务大厅]#k系统#n\t\t\t\t\r\n";
var status = -1;
var i = 0;

function start() {
    status = -1;
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
        text += 菜单行([[0, "每日任务"], [1, "主线任务"], [2, "世界任务"]]);
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

// 一行菜单：半角 [] 括号 + 空格定宽对齐（制表符宽度不可控，不要改回去）
function 菜单行(条目列表) {
    let 行 = "";
    for (let n = 0; n < 条目列表.length; n++) {
        行 += "#L" + 条目列表[n][0] + "##b[" + 条目列表[n][1] + "]#k#l";
        if (n < 条目列表.length - 1) {
            let 补 = 菜单格宽 + 菜单格间隔 - 取显示宽("[" + 条目列表[n][1] + "]");
            行 += " ".repeat(补 > 0 ? 补 : 菜单格间隔);
        }
    }
    return 行 + "\r\n";
}

// 半角宽度：中日韩全角字符按 2 计，其余按 1 计
function 取显示宽(文本) {
    let 宽 = 0;
    for (let n = 0; n < 文本.length; n++) {
        宽 += 文本.charCodeAt(n) > 0x2E80 ? 2 : 1;
    }
    return 宽;
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
            openNpc("任务/世界任务");
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
