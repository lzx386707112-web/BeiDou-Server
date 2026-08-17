/**
 * @description 共同富裕系统脚本
 */
// 导入所需的Java类
var title = "\t\t\t\t\t#e#k欢迎来到#r[共同富裕&资本富裕]#k系统#n\t\t\t\t\r\n";

const PacketCreator = Java.type('org.gms.util.PacketCreator');
const CashShop = Java.type('org.gms.server.CashShop');

var needItemId = 4039013; // 需要的道具ID
var status = -1;
var selection = 0;
var inputQuantity = 0;
var exchangeType = 0; // 0=共同富裕, 1=邪恶资本家

// 共同富裕：道具兑换比例
var COMMON_GOOD_ITEM_COST = 1; // 消耗1个道具
var COMMON_GOOD_CASH_REWARD = 100; // 全服每人获得100点券

// 邪恶资本家：道具兑换比例
var EVIL_CAPITALIST_ITEM_COST = 1; // 消耗1个道具
var EVIL_CAPITALIST_CASH_REWARD = 200; // 自己获得200点券

// 安全发放点券方法（防止溢出和负数）
function doGainCash(chr, type, quantity) {
    var cash = chr.getCashShop().getCash(type);
    var sum = cash + quantity;
    // 禁止点券小于0导致商城错误
    if (sum < 0) {
        quantity = -cash;
    }
    // 禁止点券大于最大值
    if (sum > 2147483647) { // Integer.MAX_VALUE
        quantity = 2147483647 - cash;
    }
    chr.getCashShop().gainCash(type, quantity);
}

function start() {
    action(1, 0, 0);
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
        // 主菜单
        showMainMenu();
    } else if (status === 1) {
        // 处理选择
        handleSelection(selection);
    } else if (status === 2) {
        // 输入数量确认
        handleInputConfirm(selection);
    } else if (status === 3) {
        // 最终确认兑换
        handleFinalConfirm(selection);
    } else {
        cm.dispose();
    }
}

function showMainMenu() {
    var itemName = cm.getPlayer().getItemName(needItemId);
    var playerItemCount = cm.getItemQuantity(needItemId);

    var text = title;
    text += "#k═══════════════════════════════════\r\n";
    text += "#r【玩法说明】#k\r\n";
    text += "1. 使用#i" + needItemId + "# #z" + needItemId + "# 可兑换相应点券\r\n";
    text += "2. 该道具所有怪物均有概率掉落\r\n";
    text += "3. 兑换方式分为两种，请谨慎选择\r\n";
    text += "#k═══════════════════════════════════\r\n";
    text += "#b你当前拥有：#i" + needItemId + "# #z" + needItemId + "# x #r" + playerItemCount + "#k\r\n";
    text += "\r\n";
    text += "#L0##e#b[共同富裕]#n#k\r\n";
    text += "  每消耗1个金币，" + cm.getPlayer().getClient().getChannel() + "频道所有在线玩家获得 #r" + COMMON_GOOD_CASH_REWARD + " 点券#k\r\n";
    text += "\r\n";
    text += "#L1##e#b[邪恶资本家]#n#k\r\n";
    text += "  每消耗1个金币，仅自己获得 #r" + EVIL_CAPITALIST_CASH_REWARD + " 点券#k\r\n";
    text += "\r\n";

    cm.sendSimple(text);
}

function handleSelection(sel) {
    selection = sel;
    var playerItemCount = cm.getItemQuantity(needItemId);

    if (playerItemCount < 1) {
        cm.sendOk("#e#r【兑换失败】#k#n\r\n\r\n您没有足够的 #i" + needItemId + "# #t" + needItemId + "#！\r\n请先去击杀怪物获取该道具。");
        cm.dispose();
        return;
    }

    if (selection === 0) {
        // 共同富裕
        exchangeType = 0;
        var maxExchange = Math.min(playerItemCount, 1000000); // 最多兑换100次
        var text = "\t\t\t\t\t\t\t\t\t#e#d[共同富裕 - 兑换]#k#n\t\t\t\t\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b您选择了【共同富裕】模式#k\r\n\r\n";
        text += "#i" + needItemId + "# #t" + needItemId + "# 消耗：#r" + COMMON_GOOD_ITEM_COST + " 个/次#k\r\n";
        text += cm.getPlayer().getClient().getChannel() + "频道玩家获得：#r" + COMMON_GOOD_CASH_REWARD + " 点券/次#k\r\n\r\n";
        text += "#b您当前拥有：#i" + needItemId + "# x #r" + playerItemCount + "#k\r\n";
        text += "#b最多可兑换：#r" + maxExchange + " 次#k\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b请输入兑换数量（1-" + maxExchange + "）：#k\r\n";

        cm.sendGetNumber(text, 1, 1, maxExchange);

    } else if (selection === 1) {
        // 邪恶资本家 - 支持选择数量
        exchangeType = 1;
        var maxExchange = Math.min(playerItemCount, 1000000); // 最多兑换100次
        var text = "\t\t\t\t\t\t\t\t\t#e#d[邪恶资本家 - 兑换]#k#n\t\t\t\t\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b您选择了【邪恶资本家】模式#k\r\n\r\n";
        text += "#i" + needItemId + "# #t" + needItemId + "# 消耗：#r" + EVIL_CAPITALIST_ITEM_COST + " 个/次#k\r\n";
        text += "自己获得：#r" + EVIL_CAPITALIST_CASH_REWARD + " 点券/次#k\r\n\r\n";
        text += "#b您当前拥有：#i" + needItemId + "# x #r" + playerItemCount + "#k\r\n";
        text += "#b最多可兑换：#r" + maxExchange + " 次#k\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b请输入兑换数量（1-" + maxExchange + "）：#k\r\n";

        cm.sendGetNumber(text, 1, 1, maxExchange);
    }
}

function handleInputConfirm(quantity) {
    inputQuantity = quantity;

    if (exchangeType === 0) {
        // 共同富裕模式 - 确认输入数量
        var text = "\t\t\t\t\t#e#d[共同富裕 - 确认兑换]#k#n\t\t\t\t\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b兑换数量：#r" + inputQuantity + " 次#k\r\n";
        text += "#i" + needItemId + "# #t" + needItemId + "# 消耗：#r" + (inputQuantity * COMMON_GOOD_ITEM_COST) + " 个#k\r\n";
        text += cm.getPlayer().getClient().getChannel() + "频道玩家获得：#r" + (inputQuantity * COMMON_GOOD_CASH_REWARD) + " 点券/人#k\r\n\r\n";
        text += "#b确认进行兑换吗？#k\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "\r\n#L0##e确认兑换#n#l\t\t";
        text += "#L1##e返回上一级#n#l\r\n";

        cm.sendSimple(text);
    } else if (exchangeType === 1) {
        // 邪恶资本家模式 - 确认输入数量
        var totalReward = inputQuantity * EVIL_CAPITALIST_CASH_REWARD;
        var text = "\t\t\t\t\t#e#d[邪恶资本家 - 确认兑换]#k#n\t\t\t\t\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "#b兑换数量：#r" + inputQuantity + " 次#k\r\n";
        text += "#i" + needItemId + "# #t" + needItemId + "# 消耗：#r" + (inputQuantity * EVIL_CAPITALIST_ITEM_COST) + " 个#k\r\n";
        text += "自己获得：#r" + totalReward + " 点券#k\r\n\r\n";
        text += "#b确认进行兑换吗？#k\r\n";
        text += "#k═══════════════════════════════════\r\n";
        text += "\r\n#L0##e确认兑换#n#l\t\t";
        text += "#L1##e返回上一级#n#l\r\n";

        cm.sendSimple(text);
    }
}

function handleFinalConfirm(sel) {
    if (sel === 1) {
        // 返回上一级
        status = -1;
        action(1, 0, 0);
        return;
    }

    if (exchangeType === 0) {
        // 共同富裕 - 执行兑换
        doCommonGoodExchange();
    } else if (exchangeType === 1) {
        // 邪恶资本家 - 执行兑换
        doEvilCapitalistExchange();
    }
}

function doCommonGoodExchange() {
    var playerItemCount = cm.getItemQuantity(needItemId);

    if (playerItemCount < inputQuantity) {
        cm.sendOk("#e#r【兑换失败】#k#n\r\n\r\n道具数量不足！\r\n您当前拥有：" + playerItemCount + " 个");
        cm.dispose();
        return;
    }

    // 扣除道具 - 使用负值直接扣除
    cm.gainItem(needItemId, -inputQuantity);

    // 再次检查道具是否正确扣除
    var newCount = cm.getItemQuantity(needItemId);
    if (newCount > playerItemCount - inputQuantity) {
        cm.sendOk("#e#r【兑换失败】#k#n\r\n\r\n道具扣除失败，请稍后重试！");
        cm.dispose();
        return;
    }

    var playerCount = 0;
    var totalCashReward = inputQuantity * COMMON_GOOD_CASH_REWARD; // 计算每个玩家获得的点券数量
    // 当前频道发放点券
    cm.getPlayer().getClient().getChannelServer().getPlayerStorage().getAllCharacters().forEach(function (chr) {
        doGainCash(chr, CashShop.NX_CREDIT, totalCashReward);
        playerCount++;
    });
    // 全服广播
    let channelId = cm.getPlayer().getClient().getChannel();
    let tip = `共产主义的接盘人【${cm.getPlayer().getName()}】给${channelId}频道乞丐发放了${totalCashReward}点卷,大家快感谢他！~`;
    全服通告("[共同富裕] " + tip);
    cm.getPlayer().sendBroadcast(2, "共同富裕", tip, true)

    var text = "\t\t\t\t\t#e#d[兑换成功]#k#n\t\t\t\t\r\n";
    text += "#k═══════════════════════════════════\r\n";
    text += "#b您成功兑换：#k\r\n";
    text += "#i" + needItemId + "# #t" + needItemId + "# x #r" + inputQuantity + " 个#k\r\n\r\n";
    text += "#b" + channelId + "频道 #r" + playerCount + " 名#k 玩家各获得：#r" + totalCashReward + " 点券#k\r\n";
    text += "#b总计发放：#r" + (playerCount * totalCashReward) + " 点券#k\r\n";
    text += "#k═══════════════════════════════════\r\n";
    cm.sendOk(text);
    cm.dispose();
}

function 全服通告(tip) {
    cm.getPlayer().sendFullServerBroadcast(tip);
}

function doEvilCapitalistExchange() {
    var playerItemCount = cm.getItemQuantity(needItemId);

    if (playerItemCount < inputQuantity) {
        cm.sendOk("#e#r【兑换失败】#k#n\r\n\r\n道具数量不足！\r\n您当前拥有：" + playerItemCount + " 个");
        cm.dispose();
        return;
    }

    // 扣除道具 - 使用负值直接扣除
    cm.gainItem(needItemId, -inputQuantity);

    // 再次检查道具是否正确扣除
    var newCount = cm.getItemQuantity(needItemId);
    if (newCount > playerItemCount - inputQuantity) {
        cm.sendOk("#e#r【兑换失败】#k#n\r\n\r\n道具扣除失败，请稍后重试！");
        cm.dispose();
        return;
    }

    // 计算奖励
    var totalReward = inputQuantity * EVIL_CAPITALIST_CASH_REWARD;

    // 给自己增加点券
    cm.getPlayer().getCashShop().gainCash(CashShop.NX_CREDIT, totalReward);
    let tip = `邪恶的资本家【${cm.getPlayer().getName()}】给自己发了${totalReward}点卷,大家快鄙视它！~`;
    全服通告("[资本富裕] " + tip);
    cm.getPlayer().sendBroadcast(2, "共同富裕", tip)
    var text = "\t\t\t\t\t\t\t\t\t#e#d[兑换成功]#k#n\t\t\t\t\r\n";
    text += "#k═══════════════════════════════════\r\n";
    text += "#b您成功兑换：#k\r\n";
    text += "#i" + needItemId + "# #t" + needItemId + "# x #r" + inputQuantity + " 个#k\r\n\r\n";
    text += "#b您获得奖励：#r" + totalReward + " 点券#k\r\n";
    text += "#k═══════════════════════════════════\r\n";
    text += "\r\n#r资本家从不分享，只追求自己的利益！#k\r\n";

    cm.sendOk(text);
    cm.dispose();
}
