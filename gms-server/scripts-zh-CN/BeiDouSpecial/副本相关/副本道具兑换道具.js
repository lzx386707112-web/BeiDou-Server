// 目标兑换道具集合（[道具ID, 兑换所需对应物品的数量]）
var itemSet = Array(
    Array(2022345, 1, ""),//大力药水
    Array(2022273, 1, ""),//斯士奶酪
    Array(2049115, 3, ""),//正向
    Array(4032170, 1, "(最多兑换100个)"),//红色魔石
    Array(4032171, 1, "(最多兑换100个)"),//蓝色魔石
);
//单个副本魔石最大兑换上限
var maxExchangeCount = 100;
var 兑换基础key = "副本魔石兑换";

// 三种兑换所需的物品ID（封装为数组，方便后续遍历和管理）
var needItems = Array(
    4001198,// 阿尔泰碎片
    4001246,// 温暖的阳光
    4032266 // 耀眼的阳光
);

var status = 0;
var exchangeItemId = 0;
var exchangeQty = 1;    //兑换的数量
var needItemId = 0;
var needItemCount = 1;
var totalCost = 0;

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    status++;
    // 关闭对话/取消操作
    if (mode == -1) {
        cm.dispose();
        return;
    } else if (mode == 0) {
        cm.dispose();
        return;
    }
    if (status == 1) {//展示物品
        var dialogContent = "请选择你要兑换的道具及对应兑换材料\r\n";
        dialogContent += "#b(血石和魔法石单个副本最多兑换100个，总共每种300个)#k\r\n";
        // 遍历三种兑换物品，分区域展示
        for (var n = 0; n < needItems.length; n++) {
            needItemId = needItems[n];
            // 添加当前兑换物品的标题（清晰区分）
            // 遍历目标道具，生成选项（选项编码：n*itemSet.length + i，用于后续解析）
            for (var i = 0; i < itemSet.length; i++) {
                exchangeItemId = itemSet[i][0];
                let curNeedItemCount = itemSet[i][1];
                dialogContent += "\r\n#L" + (n * itemSet.length + i) + "#"; // 唯一选项编码
                dialogContent += "#v" + exchangeItemId + "# #b#z" + exchangeItemId + "#";
                if (exchangeItemId === 4032170 || exchangeItemId === 4032171) {
                    var count = maxExchangeCount - 获取魔石已兑换数量();
                    dialogContent += `\t\t需要：#v${needItemId}# x #r${needItemCount}个 #b(还能兑换${count}个) `;
                } else {
                    dialogContent += `\t\t需要：#v${needItemId}# x #r${curNeedItemCount}个`;
                }
            }
            dialogContent += "\r\n\r\n";
        }
        cm.sendSimple(dialogContent);
    } else if (status == 2) {// 选择数量
        // 解析选项编码，获取「兑换物品索引」和「目标道具索引」
        let index = Math.floor(selection / itemSet.length);
        let selectedItemIndex = selection % itemSet.length;
        needItemId = needItems[index]; // 需要材料
        needItemCount = itemSet[selectedItemIndex][1]; // 需要单个材料数量
        exchangeItemId = itemSet[selectedItemIndex][0]; // 兑换道具
        // 发送数量输入对话框
        var confirmContent = "你选择兑换：\r\n";
        var curExchangeCount = getMaxExchangeCount();
        if (exchangeItemId === 4032170 || exchangeItemId === 4032171) {
            confirmContent += `\r\n#i${exchangeItemId}##b#t${exchangeItemId}# #r(已兑换：${获取魔石已兑换数量()}个,单个副本最大兑换：${maxExchangeCount}个)\r\n`;
        } else {
            confirmContent += `\r\n#i${exchangeItemId}##b#t${exchangeItemId}#\r\n`;
        }
        confirmContent += `#k单个消耗：#v${needItemId}# #rx ${needItemCount}个\r\n\r\n`;
        confirmContent += `#b请输入兑换个数（1~${curExchangeCount}）`;
        cm.sendGetNumber(confirmContent, 1, 1, curExchangeCount);
    } else if (status == 3) {// 二次确认
        // 处理输入数量（确保为正整数）
        exchangeQty = Math.abs(selection) > 0 ? Math.abs(selection) : 1;
        totalCost = needItemCount * exchangeQty; // 计算总消耗
        // 额外校验：防止核心变量未赋值（双重兜底）
        if (exchangeItemId == 0 || needItemId == 0 || needItemCount == 0) {
            cm.sendOk("兑换信息异常，请重新开始！");
            cm.dispose();
            return;
        }
        // 发送确认对话框
        var confirmContent = "确认兑换信息：\r\n";
        confirmContent += `\r\n兑换道具：#v${exchangeItemId}# #rx ${exchangeQty}个\r\n`;
        confirmContent += `需要：#v${needItemId}# #rx ${totalCost}个\r\n`;
        confirmContent += "是否确定兑换？";
        cm.sendYesNo(confirmContent);
    } else if (status == 4) {  // 步骤4：执行兑换逻辑（校验材料、扣减材料、发放道具）
        if (exchangeItemId == 0 || needItemId == 0 || needItemCount == 0 || totalCost == 0) {
            cm.sendOk("兑换信息异常，无法执行兑换！");
            cm.dispose();
            return;
        }
        if (!cm.haveItem(needItemId, totalCost)) {
            cm.sendOk(`需要：#v${needItemId}# x${totalCost}个，您的数量不足，无法兑换！\r\n`);
            cm.dispose();
            return;
        }
        if (!cm.canHold(exchangeItemId, exchangeQty)) {
            cm.sendOk(`背包空间不足，无法容纳兑换道具#v${exchangeItemId}# x ${exchangeQty}个`);
            cm.dispose();
            return;
        }
        if (checkoutExchange(exchangeItemId, exchangeQty)) {
            cm.gainItem(needItemId, -totalCost); // 扣减兑换材料（负数为减少）
            cm.gainItem(exchangeItemId, exchangeQty); // 发放目标道具
            let tip = `兑换成功！`;
            tip += `\r\n获得：#v${exchangeItemId}# x${exchangeQty}个,\r\n`;
            tip += `\r\n消耗：#v${needItemId}# x${totalCost}个,\r\n`;
            cm.sendOk(tip);
            sendSuperMegaphone(cm.getPlayer(), 6, "副本兑换", `恭喜玩家${cm.getPlayer().getName()}兑换了${totalCost}个【${cm.getPlayer().getItemName(exchangeItemId)}】!`);
            cm.dispose();
        }
    }
}

function checkoutExchange() {
    if (exchangeItemId === 4032170 || exchangeItemId === 4032171) {
        let count = 获取魔石已兑换数量();
        if (count >= maxExchangeCount) {
            cm.sendOk("已超出兑换上限，该道具每个副本最多只能兑换100个");
            cm.dispose();
            return false;
        }
    }
    保存魔石已兑换数量();
    return true;
}

function getMaxExchangeCount() {
    if (exchangeItemId === 4032170 || exchangeItemId === 4032171) {
        return Math.max(maxExchangeCount - 获取魔石已兑换数量(), 1);
    }
    return 100;
}

function getKey() {
    return 兑换基础key + `_${exchangeItemId}_${needItemId}`;
}

function 获取魔石已兑换数量() {
    return Number(cm.getCharacterExtendValue(getKey())) || 0;
}


function 保存魔石已兑换数量() {
    cm.saveOrUpdateCharacterExtendValue(getKey(), String(获取魔石已兑换数量() + exchangeQty));
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
