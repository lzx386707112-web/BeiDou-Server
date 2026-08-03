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
 -- Odin JavaScript --------------------------------------------------------------------------------
 VIP Cab - Victoria Road : Lith Harbor (104000000)
 -- By ---------------------------------------------------------------------------------------------
 Xterminator
 -- Version Info -----------------------------------------------------------------------------------
 1.0 - First Version by Xterminator
 ---------------------------------------------------------------------------------------------------
 **/


var itemSet = Array(
    Array(4310000, 4001126, 500),                    //（卷轴代码，材料物品代码，单个物品所需材料个数）
    Array(2340000, 4001006, 500),
    Array(2049100, 4001006, 500),
    Array(2049115, 2049100, 50),            //正向
    Array(4021010, 4020009, 50),
    // Array(4001129, 4001126, 1),            //嘉年华1纪念币
    Array(4031545, 4031543, 1),            //婚礼村沙曼先生的希望票兑换
    Array(4031545, 4031544, 1),            //婚礼村沙曼先生的希望票兑换
    Array(4031544, 4031543, 1),            //婚礼村沙曼先生的希望票兑换
//Array(4001254,4001126,2),            //嘉年华2纪念币

//Array(2040920,4001006,3),
//Array(2040816,4001006,3),
//Array(2040915,4001006,5),
    Array(5150040, 4030012, 100),
);
var status = 0;
var selectedItem;
var item;
var req;
var cost;
var qty;
var co;

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    status++;
    if (mode == -1) {
        cm.dispose();
        return;
    } else if (mode == 0) {
        // cm.sendOk("欢迎下次再来!.");
        cm.dispose();
        return;
    }
    if (status == 1) {
        var add = "请选择你想兑换的物品\r\n";
        //add += "#d点卷余额：#b" + cm.getPlayer().getCashShop().getCash(1) + "#k          ";
        //add += "#d抵用余额：#b" + cm.getPlayer().getCashShop().getCash(4) + "#k#n\r\n";
        for (var i = 0; i < itemSet.length; i++) {
            add += "\r\n#L" + i + "##v " + itemSet[i][0] + "##z";
            add += itemSet[i][0] + "#" + "    需要材料:#v " + itemSet[i][1] + `#(1:${itemSet[i][2]})`;
            //add += "   需要个数: " + itemSet[i][2]+"个#l#k";
        }
        ;

        cm.sendSimple(add);
    } else if (status == 2) {

        selectedItem = selection;
        item = itemSet[selectedItem][0];
        req = itemSet[selectedItem][1];
        co = itemSet[selectedItem][2];
        var bdd = "你确定要兑换\r\n";
        bdd += "\r\n#i" + item + "# " + " #t" + item + "#";
        bdd += "    需要材料:#v " + req + "\r\n\r\n";
        bdd += "单个物品需要材料个数:#r " + co + "个\r\n\r\n\r\n";
        bdd += "请输入购买个数\r\n";
        cm.sendGetNumber(bdd, 1, 1, 100)
        //cm.sendYesNo(bdd);
    } else if (status == 3) {
        qty = (selection > 0) ? selection : (selection < 0 ? -selection : 1);
        cost = co * qty;   //花费为物品单价*输入的数量
        if (!cm.haveItem(req, cost)) {
            cm.sendOk("#b您的材料不足");
            cm.dispose();
        } else {
            cm.gainItem(req, -cost);
            cm.gainItem(item, qty);
            sendRandomSceneMegaphone(cm.getPlayer(), 6, "金币兑换", `恭喜玩家${cm.getPlayer().getName()}兑换了${qty}个【${cm.getPlayer().getItemName(item)}】!`);
            cm.sendOk("#b购买成功");
            cm.dispose();
        }
        cm.dispose();
    }
}
function sendRandomSceneMegaphone(player, typeOrTitle, titleOrContent, content) {
    if (player.checkoutBroadcast()) {
        return;
    }
    var title = content === undefined ? typeOrTitle : titleOrContent;
    var message = content === undefined ? titleOrContent : content;
    var fullMessage = "[" + title + "] : " + message;
    var lineLength = Math.max(1, Math.ceil(fullMessage.length / 4));
    var lines = new (Java.type("java.util.LinkedList"))();
    for (var i = 0; i < 4; i++) {
        var start = i * lineLength;
        lines.add(start < fullMessage.length
            ? fullMessage.substring(start, Math.min(start + lineLength, fullMessage.length))
            : "");
    }

    var itemIds = [5390005, 5390001, 5390002];
    var itemId = itemIds[Math.floor(Math.random() * itemIds.length)];
    var Server = Java.type("org.gms.net.server.Server");
    var PacketCreator = Java.type("org.gms.util.PacketCreator");
    var world = player.getWorld();
    Server.getInstance().broadcastMessage(
        world,
        PacketCreator.getAvatarMega(player, "", player.getClient().getChannel(), itemId, lines, true)
    );

    var clearTask = new (Java.type("java.lang.Runnable"))({
        run: function () {
            Server.getInstance().broadcastMessage(world, PacketCreator.byeAvatarMega());
        }
    });
    Java.type("org.gms.server.TimerManager").getInstance().schedule(clearTask, 10000);
}
