var itemSet = Array(
    Array(4031698, 10000000),
    Array(4031709, 10000000),
    Array(4001163, 20000000),
    Array(4000313, 500000),                     //（物品代码，金币数）
    Array(4001086, 20000000),
    Array(3992041, 20000000),
    Array(5150044, 20000000),
    Array(4006000, 10000),
    Array(4006001, 10000),
    Array(4031179, 8000000),
    Array(4001017, 10000000),
    Array(4001107, 1000000),
    Array(4161021, 1000000),
    Array(4161018, 1000000),
    Array(4161015, 1000000),
    Array(4161016, 1000000),
    Array(4001110, 1000000),
    Array(4001111, 1000000),
    Array(4001112, 1000000),
    Array(4039020, 10000000),
);

//金蛋
var 金币道具 = 4039020;
var 兑换后的金币比例 = 950;

var status = 0;
var selectedItem;
var item;
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
        var add = "请选择你想购买的物品\r\n";
        add += "#d金币余额：#b" + cm.getMeso() + "#k          ";
        for (var i = 0; i < itemSet.length; i++) {
            add += "\r\n#L" + i + "##v " + itemSet[i][0] + "#";
            add += "         需要金币:" + itemSet[i][1] / 10000 + "万";
        }
        add += "\r\n#L1000# #b兑换金币" + 兑换后的金币比例 + "万#k";
        add += "         需要道具:#v " + 金币道具 + "#x1";
        cm.sendSimple(add);
    } else if (status == 2) {
        selectedItem = selection;
        if (selectedItem === 1000) {
            item = 金币道具;
            var bdd = `这里可以使用#i${item}##t${item}# x1 来进行兑换${兑换后的金币比例}万金币\r\n`;
            bdd += `请输入兑换几次${兑换后的金币比例}万\r`;
            cm.sendGetNumber(bdd, 1, 1, 100)
        } else {
            item = itemSet[selectedItem][0];
            co = itemSet[selectedItem][1];
            var bdd = "你想要兑换：\r\n";
            bdd += "\r\n#i" + item + "# " + " #t" + item + "#";
            bdd += "单个物品需要金币:#r " + co / 10000 + "万\r\n\r\n\r\n";
            bdd += "请输入购买个数\r\n";
            cm.sendGetNumber(bdd, 1, 1, 100)
        }
    } else if (status == 3) {
        qty = (selection > 0) ? selection : (selection < 0 ? -selection : 1);
        if (selectedItem === 1000) {
            //金蛋兑金币
            cm.sendYesNo("你确定要兑换：" + qty + `个 ${兑换后的金币比例}万吗？需要道具#b#t` + 金币道具 + "# " + qty + "个#k？\r\n");
        } else {
            cm.sendYesNo("你确定要兑换：" + qty + "个#b#t" + item + "##k吗？\r\n");
        }
    } else if (status == 4) {
        if (selectedItem === 1000) {//金蛋兑金币
            if (cm.haveItem(金币道具, qty)) {
                cm.gainItem(金币道具, -qty);
                cm.gainMeso(qty * 兑换后的金币比例 * 10000);
            } else {
                cm.sendOk("金蛋不足，无法兑换。");
            }
        } else {
            cost = co * qty;   //花费为物品单价*输入的数量
            if (cm.getMeso() < cost) {
                cm.sendOk("金币不足。");
            } else {
                if (cm.canHold(item, qty)) {
                    cm.gainMeso(-cost);
                    cm.gainItem(item, qty);
                    sendRandomSceneMegaphone(cm.getPlayer(), 6, "金币兑换", `恭喜玩家${cm.getPlayer().getName()}兑换了${qty}个【${cm.getPlayer().getItemName(item)}】!`);
                    cm.sendOk("购买成功。");
                }else {
                    cm.sendOk("背包空间不足。");
                }
            }
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
