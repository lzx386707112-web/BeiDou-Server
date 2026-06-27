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
var OldTitle = "\t\t\t\t\t#e欢迎来到#rBeiDou#k脚本中心#n\t\t\t\t\r\n";
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
        text += "当前点券：" + cm.getPlayer().getCashShop().getCash(1) + "\r\n";
        text += "当前抵用券：" + cm.getPlayer().getCashShop().getCash(2) + "\r\n";
        text += "当前信用券：" + cm.getPlayer().getCashShop().getCash(4) + "\r\n";
        text += " \r\n";
        text += "#b  注：点击NPC无反应可输入 @dispose 来解卡#k\r\n\r\n";
        text += "#d  【随着等级提升，将自动开放更多便捷功能】#k\r\n";

        text += "#L0#新人福利#l \t #L1#每日签到#l\t #L2#在线奖励#l\r\n";

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L15#随身仓库#l\t #L4#皇家发型#l\t #L5#时尚点装#l\r\n";
        }

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L9#快速转职#l\t #L12#血衣合成#l \t #L16#删除道具#l\r\n";
        }

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L6#便利商店#l \t #L25#怪物卡戒#l\t #L11#爆率一览#l\r\n";
        }

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L3#万能传送#l \t #L14#金币兑换#l\t #L10#三宠技能#l\r\n";
        }

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L13#物品兑换#l\t #L7#卷轴商店#l\t #L27#Boss成长#l\r\n";
        }

        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L8#大药商店#l\t #L22#技能全满#l \t #L23#更换职业#l\r\n";
        }
        if (cm.getPlayer().getLevel() >= 10) {
            text += "#L99#二段跳#l\t #L26#龙神技能#l\t #L24#一键转生#l\r\n";
        }


        //text += " \r\n 以下是暂不支持的脚本：\r\n";
        //text += "#L18#矿石仓库#l\t #L19#道具抽奖#l \t #L20#音乐点播#l\t #l\r\n";
        //text += "#L21#战力系统#l\t #L24#一键转生#l\r\n";
        // 从083V2无法移植的脚本： 矿石仓库，道具抽奖，音乐点播，战力系统，

        if (cm.getPlayer().isGM()) {
            text += "\r\n";
            text += "\t\t\t\t#r=====以下内容仅GM可见=====\r\n";
            text += "#L62#GM商店集合      #l \t #L63#整容集合#l\r\n";
            text += "#L65#一键删除道具#l \t     #L66#一键刷道具#l\r\n";
            text += "#L67#有状态脚本示例#l \t #L68#NextLevel脚本示例#l";
        }
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        // 非GM功能
        //       case 0:
        //           cm.getPlayer().saveLocation("FREE_MARKET");
        //           cm.warp(910000000, "out00");
        //           break;
        // 脚本移植注意编码改为UTF-8
        case 99:
            openNpc("快捷技能");
            break;
        case 0:
            openNpc("新人福利");
            break;
        case 1:
            openNpc("每日签到");
            break;
        case 2:
            openNpc("在线奖励");
            break;
        case 3:
            openNpc("万能传送");
            break;
        case 4:
            openNpc("皇家发型");
            break;
        case 5:
            openNpc("时尚点装");
            break;
        case 6:
            cm.openShopNPC(9201099); //便利商店
            cm.dispose();
            break;
        case 7:
            cm.dispose();
            cm.openShopNPC(2082014); //卷轴商店
            cm.dispose();
            break;
        case 8:
            cm.openShopNPC(9201101);  //大药商店
            cm.dispose();
            break;
        case 9:
            openNpc("快速转职");
            break;
        case 10:
            openNpc("三宠技能");
            break;
        case 11:
            openNpc("爆率一览");
            break;
        case 12:
            openNpc("血衣合成");
            break;
        case 13:
            openNpc("物品兑换");
            break;
        case 14:
            openNpc("金币兑换");
            break;
        case 15:
            openNpc("随身仓库");
            break;
        case 16:
            openNpc("删除道具");
            break;
        case 17:
            openNpc("益智答题");
            break;
        //       case 18:
        //           openNpc("矿石仓库");
        //           break;
        //       case 19:
        //           openNpc("道具抽奖");
        //           break;
        //       case 20:
        //           openNpc("音乐点播");
        //           break;
        //      case 21:
        //         openNpc("战力系统");
        //         break;
        case 22:
            openNpc("技能全满");
            break;
        case 23:
            openNpc("更换职业");
            break;
        case 24:
            openNpc("一键转生");
            break;

        case 25:
            openNpc("2006");  //明珠港怪物卡戒指NPC
            break;
        case 26:
            openNpc("龙神技能面板");
            break;
        case 27:
            openNpc("Boss成长系统");
            break;

        // GM功能
        case 62:
            openNpc("GM商店");
            break;
        case 63:
            openNpc("Salon");
            break;
//        case 64:
//            openNpc("UI查询");
//           break;
        case 65:
            openNpc("一键删除道具");
            break;
        case 66:
            openNpc("一键刷道具");
            break;
        case 67:
            openNpc("Example1")
            break;
        case 68:
            openNpc("Example2")
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
