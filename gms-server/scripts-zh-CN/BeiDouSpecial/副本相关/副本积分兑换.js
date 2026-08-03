var itemSet = Array(
    Array(4001163, 1),//紫色魔力晶石
    Array(2022345, 1),//大力药水
    Array(2022273, 2),//土司奶酪
    // Array(2022282, 2),//玛瑙苹果
    // Array(2022282, 4),//恶魔药剂
    Array(2340000, 3),//祝福
    Array(2049100, 3),//混沌
    Array(2049115, 10),//正向
    Array(4039020, 3),//金蛋
    Array(4032133, 5),//红钻
    Array(4032170, 5),//红色魔石
    Array(4032171, 5),//蓝色魔石
    Array(4260009, 5),//强化宝石
    Array(4260010, 1),//强化宝石碎片
    Array(5211048, 30),//双倍
    Array(2029002, 30),//双爆
    Array(4251200, 50),//五彩下
    Array(4251201, 250),//五彩中
    Array(4251202, 500),//五彩高
    Array(1102871, 250),//扎披
    Array(1132296, 250),//扎腰带
    Array(1003450, 500),//品克缤帽子
    Array(4001198, 5),//阿尔泰碎片
    Array(4001246, 5),//温暖的阳光
    Array(4032266, 5),//闪耀的阳光  4032266
    Array(4001254, 2),//闪耀的纪念币
);

var status = 0;
var selectedItem;
var item;
var cost;
var qty;
var co;
var TimeUnit = Java.type('java.util.concurrent.TimeUnit');

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
        var add = "请选择你要兑换的道具\r\n";
        add += "#d剩余积分余额：#b" + cm.getPqPoints() + "#k          ";
        for (var i = 0; i < itemSet.length; i++) {
            // add += "\r\n#L" + i + "##v " + itemSet[i][0] + "#";
            // add += "         需要积分:" + itemSet[i][1];
            add += `\r\n#L${i}##v${itemSet[i][0]}# #b#z${itemSet[i][0]}#  #k需要积分 #bx ${itemSet[i][1]}#k`;
        }
        cm.sendSimple(add);
    } else if (status == 2) {
        selectedItem = selection;
        item = itemSet[selectedItem][0];
        co = itemSet[selectedItem][1];
        var bdd = "你想要兑换：\r\n";
        bdd += "\r\n#i" + item + "# " + " #t" + item + "#";
        bdd += " 单个物品需要积分:#r " + co + "\r\n\r\n\r\n";
        bdd += "请输入兑换个数\r\n";
        cm.sendGetNumber(bdd, 1, 1, 100)
    } else if (status == 3) {
        qty = (selection > 0) ? selection : (selection < 0 ? -selection : 1);
        cm.sendYesNo("你确定要兑换：" + qty + "个#b#t" + item + "##k吗？\r\n");
    } else if (status == 4) {
        cost = co * qty;   //花费为物品单价*输入的数量
        if (cm.getPqPoints() < cost) {
            cm.sendOk("积分不足。");
        } else {
            if (cm.canHold(item, qty)) {
                cm.consumptionPqPoints(cost);
                if (item == 5211048) {
                    var expireTime = TimeUnit.MINUTES.toMillis(240);
                    cm.gainItem(item, qty, false, true, expireTime);
                } else {
                    cm.gainItem(item, qty);
                }
                cm.sendOk("兑换成功。");
                sendRandomSceneMegaphone(cm.getPlayer(), 6, "副本兑换", `恭喜玩家${cm.getPlayer().getName()}兑换了一个【${cm.getPlayer().getItemName(item)}】!`);
            } else {
                cm.sendOk("背包空间不足。");
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
