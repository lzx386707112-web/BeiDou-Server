var itemSet = Array(
    Array(2049116, 4031635, 4),
    Array(2049116, 4031643, 4),
    Array(2049116, 4031639, 4),
    Array(2049116, 4031647, 4),
    Array(4031629, 4031647, 1),
    Array(4031632, 4031647, 1),
    Array(4039020, 4031635, 1),
    Array(4039020, 4031643, 1),
    Array(4039020, 4031639, 1),
    Array(4039020, 4031647, 1),
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
        for (let i = 0; i < itemSet.length; i++) {
            const itemRow = itemSet[i] || [];
            const targetId = itemRow[0] || 0;
            const needId = itemRow[1] || 0;
            const needNum = itemRow[2] || 0;
            add += "\r\n";
            add += `#b#L${i}##v${targetId}##z${targetId}#    需要:#v${needId}##z${needId}##r(${needNum}个)`;
        }
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
            sendSuperMegaphone(cm.getPlayer(), 6, "金币兑换", `恭喜玩家${cm.getPlayer().getName()}兑换了${qty}个【${cm.getPlayer().getItemName(item)}】!`);
            cm.sendOk("#b购买成功");
            cm.dispose();
        }
        cm.dispose();
    }
}
function sendSuperMegaphone(player, typeOrTitle, titleOrContent, content) {
    if (player.checkoutBroadcast()) {
        return;
    }
    var title = content === undefined ? typeOrTitle : titleOrContent;
    var message = content === undefined ? titleOrContent : content;
    var fullMessage = "[" + title + "] : " + message;
    var Server = Java.type("org.gms.net.server.Server");
    var PacketCreator = Java.type("org.gms.util.PacketCreator");

    // 5072000（高质地喇叭）使用类型 3 的全服喇叭封包。
    Server.getInstance().broadcastMessage(
        player.getWorld(),
        PacketCreator.serverNotice(
            3,
            player.getClient().getChannel(),
            player.getName() + " : " + fullMessage,
            true
        )
    );
}
