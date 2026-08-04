// 目标兑换道具集合（[道具ID, 所需累计积分，描述]）
var itemSet = Array(
    Array(1142700, 50, ""),//   10
    Array(1142701, 100, ""),//  20
    Array(1142702, 150, ""),//  40
    Array(1142703, 200, ""),//  60
    Array(1142704, 300, ""),//  80
    Array(1142705, 400, ""),//  120
    Array(1142706, 500, ""),//   200
);
const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
var status = 0;
var 累计奖励基础key = "副本积分累计奖励v1_";
var index; // 选中的道具在itemSet中的索引
let targetItem = null;      // 材料装备

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    // 关闭对话/取消操作（优先处理，避免无效流程）
    if (mode == -1) {
        cm.dispose();
        return;
    } else if (mode == 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 1) {
        let text = ""; // 空行优化格式
        text += "#b请选择你要兑换的累计奖励：\r\n";
        text += "#b当前累计副本积分：#r" + cm.getPqTotalPoints() + "#k\r\n";
        text += "#b从小肝怡情开始可继承上一个勋章的红钻洗练和星级强化#r#k\r\n";
        // 遍历itemSet，生成兑换选项列表
        for (var i = 0; i < itemSet.length; i++) {
            var itemInfo = itemSet[i];
            var itemId = itemInfo[0];
            var needPoints = itemInfo[1];
            // var itemDesc = itemInfo[2] || "";
            var statusStr = 判断是否已领取(itemId) ? '#d(已领取)#k' : '#r(未领取)#k';
            text += "\r\n#L" + i + "#";
            text += `#v${itemId}# #z${itemId}# 需要累计积分 #bx ${needPoints}\t${statusStr}\r\n`;

        }
        cm.sendSimple(text);
    } else if (status === 2) { // 处理用户选择的道具
        index = selection; // 赋值选中的道具索引
        // 校验选择是否有效（防止越界）
        if (index < 0 || index >= itemSet.length) {
            cm.sendOk("无效的选择，请重新操作！");
            cm.dispose();
            return;
        }
        doSelect(); // 执行核心兑换逻辑
    } else {
        cm.dispose(); // 多余状态直接关闭对话
    }
}

/**
 * 生成角色扩展信息的key（累计奖励_+道具id）
 */
function getKey(itemId) {
    return 累计奖励基础key + `${itemId}`;
}

/**
 * 判断指定道具是否已领取
 */
function 判断是否已领取(itemId) {
    return cm.getCharacterExtendValue(getKey(itemId)) === "1";
}

/**
 * 保存道具领取信息（标记为已领取）
 */
function 保存领取信息(itemId) {
    cm.saveOrUpdateCharacterExtendValue(getKey(itemId), "1"); // 存储为字符串"1"，保持一致性
}

/**
 * 核心兑换逻辑：校验积分、校验领取状态、发放道具
 */
function doSelect() {
    // 1. 获取当前选中道具的信息
    var currentItem = itemSet[index];
    var itemId = currentItem[0];
    var needPoints = currentItem[1];
    var currentTotalPoints = cm.getPqTotalPoints(); // 当前累计积分
    var isReceived = 判断是否已领取(itemId); // 是否已领取
    // 2. 校验：是否已领取
    if (isReceived) {
        cm.sendOk("该奖励【#t" + itemId + "#】已领取，无法重复兑换！");
        cm.dispose();
        return;
    }
    // 3. 校验：累计积分是否充足
    if (currentTotalPoints < needPoints) {
        cm.sendOk("累计副本积分不足！\r\n当前积分：" + currentTotalPoints + "\r\n所需积分：" + needPoints);
        cm.dispose();
        return;
    }
    const player = cm.getPlayer();
    if (index > 0) {
        var needItemId = itemSet[index - 1][0];
        targetItem = player.getInventory(InventoryType.EQUIP).getItem(1);
        if (!targetItem || targetItem.getItemId() !== needItemId) {
            cm.sendOk(`需要把勋章#v${needItemId}#[#z${needItemId}#]放在第一格`);
            cm.dispose();
            return;
        }
    }
    if (!cm.canHold(itemId, 1)) {
        cm.sendOk("背包空间不足，无法领取奖励！");
        cm.dispose();
        return;
    }
    //发放道具
    const newItem = cm.gainItem(itemId, 1);
    if (!newItem) {
        cm.sendOk("制作失败：无法生成目标物品！");
        cm.dispose();
        return;
    }
    newItem.setFlag(1); // 上锁
    // 武器属性继承逻辑
    if (targetItem) {
        newItem.replaceData(targetItem);
        // 移除原材料装备
        InventoryManipulator.removeFromSlot(
            player.getClient(),
            InventoryType.EQUIP,
            targetItem.getPosition(),
            1,
            false
        );
    }
    player.forceUpdateItem(newItem); // 强制更新装备状态
    // 制作成功提示+广播
    保存领取信息(itemId);
    cm.sendOk(`恭喜领取道具：#b#t${itemId}#`);
    sendSuperMegaphone(cm.getPlayer(), 3, "副本兑换", `恭喜肝神【${cm.getPlayer().getName()}】领取累计副本奖励【${cm.getPlayer().getItemName(itemId)}】!`);
    cm.dispose();
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
