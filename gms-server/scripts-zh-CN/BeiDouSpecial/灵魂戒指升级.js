var status = -1;
// Java工具类
var ItemInformationProvider = Java.type('org.gms.server.ItemInformationProvider');
var InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
var InventoryType = Java.type('org.gms.client.inventory.InventoryType');

// ====================== 配置区 ======================
var RING_START_ID = 1118000;//灵魂戒指初始ID
var RING_MAX_ID = 1118042;//灵魂戒指最大ID
var EXCHANGE_MATERIAL_ID = 4000019;//兑换1级戒指所需材料
var EXCHANGE_MATERIAL_NUM = 1000;//兑换1级戒指所需材料数量
var UPGRADE_MATERIAL_ID = 4310059;//升级所需材料
var UPGRADE_COST_MESO = 50000000;//所需金币
var INIT_RATE = 0.80;    // 初始80%
var RATE_DOWN = 0.05;   // 每次递减5%
var MIN_RATE = 0.15;    // 最低15%
var ADD_4STAT = 5;      // 四维力敏智运+5
var ADD_WATK = 5;       // 物攻+5
var ADD_MATK = 10;      // 魔攻+10
// ===================================================

var ringCache = [];
var selectSlot = -1;
var selectRingId = -1;
var exchangeMode = false;
var 金币图标 = "#fUI/UIWindow.img/QuestIcon/7/0#";

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === -1) {
        cm.dispose();
        return;
    }
    if (mode === 1) status++;
    else status--;

    if (status === 0) {
        scanAllRing();
        let totalRingCount = countAllSoulRings();
        if (totalRingCount > 1) {
            cm.sendOk("角色的装备栏或已穿戴栏中存在多个灵魂戒指，每个角色只能拥有1个，无法升级！");
            cm.dispose();
            return;
        }
        if (totalRingCount <= 0) {
            exchangeMode = true;
            cm.sendYesNo(`当前背包中没有灵魂戒指。\r\n\r\n是否使用 #v${EXCHANGE_MATERIAL_ID}##t${EXCHANGE_MATERIAL_ID}# × ${EXCHANGE_MATERIAL_NUM}\r\n兑换 #v${RING_START_ID}##t${RING_START_ID}#？`);
            return;
        }
        if (ringCache.length <= 0) {
            cm.sendOk("灵魂戒指正在穿戴中，请先取下放入装备栏后再来升级。");
            cm.dispose();
            return;
        }
        let text = "#e【灵魂戒指升级系统】#n\r\n\r\n";
        text += "每次升级加成：#r全属性/物攻+5，魔攻+10#k\r\n\r\n";
        text += "请选择需要升级的戒指：\r\n";
        for (let i = 0; i < ringCache.length; i++) {
            let r = ringCache[i];
            text += `#L${i}##v${r.id}##t${r.id}##l\r\n`;
        }
        cm.sendSimple(text);
    } else if (status === 1) {
        if (exchangeMode) {
            exchangeFirstRing();
            cm.dispose();
            return;
        }
        selectSlot = ringCache[selection].slot;
        selectRingId = ringCache[selection].id;
        let nextId = selectRingId + 1;
        if (nextId > RING_MAX_ID) {
            cm.sendOk("该戒指已是最高阶，无法继续升级！");
            cm.dispose();
            return;
        }
        let targetLevel = nextId - RING_START_ID + 1;
        let upgradeMaterialNum = targetLevel;
        // 校验材料金币
        let lackText = "";
        let haveGold = cm.getMeso();
        if (cm.getItemQuantity(UPGRADE_MATERIAL_ID) < upgradeMaterialNum) {
            lackText += `缺少材料 #v${UPGRADE_MATERIAL_ID}##t${UPGRADE_MATERIAL_ID}# x${upgradeMaterialNum}\r\n`;
        }
        if (haveGold < UPGRADE_COST_MESO) {
            lackText += `金币不足，需要${UPGRADE_COST_MESO / 10000}万，当前持有${Math.floor(haveGold / 10000)}万\r\n`;
        }
        if (lackText !== "") {
            cm.sendOk(lackText);
            cm.dispose();
            return;
        }
        // 计算成功率
        let level = selectRingId - RING_START_ID;
        let nowRate = Math.max(MIN_RATE, INIT_RATE - level * RATE_DOWN);
        let confirm = "#e确认升级#n\r\n";
        confirm += `当前戒指：#v${selectRingId}##t${selectRingId}#\r\n`;
        confirm += `升级成功：#v${nextId}##t${nextId}#\r\n\r\n`;
        confirm += `本次成功率：${(nowRate * 100).toFixed(0)}%\r\n\r\n`;
        confirm += `消耗道具：#v${UPGRADE_MATERIAL_ID}##t${UPGRADE_MATERIAL_ID}# × ${upgradeMaterialNum}\r\n\r\n\r\n`;
        confirm += `消耗金币：${金币图标} ${UPGRADE_COST_MESO / 10000}万 (持有${Math.floor(haveGold / 10000)}万)\r\n\r\n`;
        confirm += "是否确认升级？";
        cm.sendYesNo(confirm);
    } else if (status === 2) {
        doUpgrade();
        cm.dispose();
    } else {
        cm.dispose();
    }
}

// 背包中没有灵魂戒指时兑换1级戒指
function exchangeFirstRing() {
    if (countAllSoulRings() > 0) {
        cm.sendOk("角色已经拥有灵魂戒指，每个角色只能拥有1个，无法再次兑换。");
        return;
    }
    if (cm.getItemQuantity(EXCHANGE_MATERIAL_ID) < EXCHANGE_MATERIAL_NUM) {
        cm.sendOk(`材料不足，需要 #v${EXCHANGE_MATERIAL_ID}##t${EXCHANGE_MATERIAL_ID}# × ${EXCHANGE_MATERIAL_NUM}。`);
        return;
    }
    if (!cm.canHold(RING_START_ID, 1)) {
        cm.sendOk("装备栏空间不足，请整理后再来兑换。");
        return;
    }
    cm.gainItem(EXCHANGE_MATERIAL_ID, -EXCHANGE_MATERIAL_NUM);
    cm.gainItem(RING_START_ID, 1);
    cm.sendOk(`兑换成功！获得 #v${RING_START_ID}##t${RING_START_ID}#。`);
}

// 统计装备背包和已穿戴栏中的灵魂戒指
function countAllSoulRings() {
    let count = 0;
    let equipInv = cm.getInventory(1);
    let maxSlot = equipInv.getSlotLimit();
    for (let s = 1; s <= maxSlot; s++) {
        let item = equipInv.getItem(s);
        if (item != null && isSoulRing(item.getItemId())) count++;
    }

    let equippedInv = cm.getInventory(-1);
    for (let s = -1; s >= -199; s--) {
        let item = equippedInv.getItem(s);
        if (item != null && isSoulRing(item.getItemId())) count++;
    }
    return count;
}

function isSoulRing(itemId) {
    return itemId >= RING_START_ID && itemId <= RING_MAX_ID;
}

// 扫描装备栏所有灵魂戒指（复刻勋章淬炼扫描方式）
function scanAllRing() {
    ringCache = [];
    let inv = cm.getInventory(1);
    let maxSlot = inv.getSlotLimit();
    let iip = ItemInformationProvider.getInstance();
    for (let s = 1; s <= maxSlot; s++) {
        let item = inv.getItem(s);
        if (item == null) continue;
        let id = item.getItemId();
        if (id >= RING_START_ID && id <= RING_MAX_ID) {
            ringCache.push({
                slot: s,
                id: id,
                name: iip.getName(id)
            });
        }
    }
}

// 执行升级核心逻辑
function doUpgrade() {
    if (countAllSoulRings() !== 1) {
        cm.sendOk("角色必须且只能拥有1个灵魂戒指才能升级！");
        return;
    }
    let inv = cm.getInventory(1);
    let oldItem = inv.getItem(selectSlot);
    if (oldItem == null || oldItem.getItemId() !== selectRingId) {
        cm.sendOk("操作失败，戒指已被移动！");
        return;
    }
    let newRingId = selectRingId + 1;
    let targetLevel = newRingId - RING_START_ID + 1;
    let upgradeMaterialNum = targetLevel;
    if (cm.getItemQuantity(UPGRADE_MATERIAL_ID) < upgradeMaterialNum || cm.getMeso() < UPGRADE_COST_MESO) {
        cm.sendOk("升级材料或金币不足！");
        return;
    }
    let player = cm.getPlayer();
    // 扣除消耗
    cm.gainItem(UPGRADE_MATERIAL_ID, -upgradeMaterialNum);
    cm.gainMeso(-UPGRADE_COST_MESO);

    let level = selectRingId - RING_START_ID;
    let nowRate = Math.max(MIN_RATE, INIT_RATE - level * RATE_DOWN);
    let success = Math.random() < nowRate;
    let oldName = ItemInformationProvider.getInstance().getName(selectRingId);

    if (success) {
        // 删除旧戒指
        InventoryManipulator.removeFromSlot(cm.getClient(), InventoryType.EQUIP, selectSlot, 1, false);
        // 仅四维+5 物攻+5 魔攻+10，其余完全继承原数值不增加
        let str = oldItem.getStr() + ADD_4STAT;
        let dex = oldItem.getDex() + ADD_4STAT;
        let int = oldItem.getInt() + ADD_4STAT;
        let luk = oldItem.getLuk() + ADD_4STAT;
        let hp = oldItem.getHp();
        let mp = oldItem.getMp();
        let watk = oldItem.getWatk() + ADD_WATK;
        let matk = oldItem.getMatk() + ADD_MATK;
        let wdef = oldItem.getWdef();
        let mdef = oldItem.getMdef();
        let acc = oldItem.getAcc();
        let avoid = oldItem.getAvoid();
        let speed = oldItem.getSpeed();
        let jump = oldItem.getJump();

        // 生成新戒指
        cm.getPlayer().gainEquip(
            newRingId,
            str, dex, int, luk,
            0, 0,
            watk, matk,
            hp, mp, wdef, mdef, acc, avoid,
            speed, jump, -1
        );
        let newName = ItemInformationProvider.getInstance().getName(newRingId);
        cm.sendOk(`升级成功！获得【#v${newRingId}##t${newRingId}#】\n四维+5 物攻+5 魔攻+10`);
        let notice = `恭喜玩家【${player.getName()}】将【${oldName}】升级为【${newName}】，全属性+5，物攻+5，魔攻+10！`;
        sendRandomSceneMegaphone(player, 2, "灵魂戒指升级", notice);
        sendServerMsg(notice);
        player.dropMessage(6, notice);
    } else {
        cm.sendOk(`升级失败！`);
        let notice = `倒霉孩子【${player.getName()}】升级【${oldName}】失败！`;
        sendRandomSceneMegaphone(player, 3, "灵魂戒指升级", notice);
        sendServerMsg(notice);
        player.dropMessage(6, notice);
    }
}

// 全服广播
function sendServerMsg(text) {
    cm.getPlayer().sendFullServerBroadcast("[灵魂戒指升级] " + text);
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
