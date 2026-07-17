var status = -1;
var ItemInformationProvider = Java.type('org.gms.server.ItemInformationProvider');
var InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
var InventoryType = Java.type('org.gms.client.inventory.InventoryType');

// ====================== 配置区 ======================
var BASE_RING_ID = 1118042;          // 第一级升级所需的原戒指
var RING_START_ID = 1118043;         // 苍穹霸主戒1级
var RING_MAX_ID = 1118062;           // 苍穹霸主戒最高级
var FIRST_MATERIAL_ID = 4000019;     // 第一级额外材料
var FIRST_MATERIAL_NUM = 1000;
var UPGRADE_MATERIAL_ID = 4310059;   // 等级 × 50
var MATERIAL_PER_LEVEL = 50;
var FIRST_UPGRADE_COST = 50000000;
var NORMAL_UPGRADE_COST = 25000000;
var FIRST_UPGRADE_RATE = 1.00;
var NORMAL_UPGRADE_RATE = 0.15;
var ADD_4STAT = 5;
var ADD_WATK = 5;
var ADD_MATK = 10;
// ===================================================

var ringCache = [];
var selectSlot = -1;
var selectRingId = -1;
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
        let totalRingCount = countAllSkyLordRings();
        if (totalRingCount > 1) {
            cm.sendOk("角色的装备栏或已穿戴栏中存在多个苍穹霸主戒，每个角色只能拥有1个，无法升级！");
            cm.dispose();
            return;
        }
        if (ringCache.length <= 0) {
            if (totalRingCount > 0) {
                cm.sendOk("苍穹霸主戒正在穿戴中，请先取下放入装备栏后再来升级。");
            } else {
                cm.sendOk(`装备栏中没有可升级的 #v${BASE_RING_ID}##t${BASE_RING_ID}#。`);
            }
            cm.dispose();
            return;
        }

        let text = "#e【苍穹霸主戒升级系统】#n\r\n\r\n";
        text += "骚年，想装逼吗\r\n";
        text += "每次升级加成：#r四维+5、物攻+5、魔攻+10#k\r\n";
        text += "升级失败只扣除材料和金币，戒指保留。\r\n\r\n";
        text += "请选择需要升级的戒指：\r\n";
        for (let i = 0; i < ringCache.length; i++) {
            let ring = ringCache[i];
            text += `#L${i}##v${ring.id}##t${ring.id}##l\r\n`;
        }
        cm.sendSimple(text);
    } else if (status === 1) {
        if (selection < 0 || selection >= ringCache.length) {
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
        let materialNum = targetLevel * MATERIAL_PER_LEVEL;
        let isFirstUpgrade = selectRingId === BASE_RING_ID;
        let upgradeCost = isFirstUpgrade ? FIRST_UPGRADE_COST : NORMAL_UPGRADE_COST;
        let nowRate = isFirstUpgrade ? FIRST_UPGRADE_RATE : NORMAL_UPGRADE_RATE;
        let lackText = "";
        let haveGold = cm.getMeso();

        if (isFirstUpgrade && cm.getItemQuantity(FIRST_MATERIAL_ID) < FIRST_MATERIAL_NUM) {
            lackText += `缺少材料 #v${FIRST_MATERIAL_ID}##t${FIRST_MATERIAL_ID}# × ${FIRST_MATERIAL_NUM}\r\n`;
        }
        if (cm.getItemQuantity(UPGRADE_MATERIAL_ID) < materialNum) {
            lackText += `缺少材料 #v${UPGRADE_MATERIAL_ID}##t${UPGRADE_MATERIAL_ID}# × ${materialNum}\r\n`;
        }
        if (haveGold < upgradeCost) {
            lackText += `金币不足，需要${upgradeCost / 10000}万，当前持有${Math.floor(haveGold / 10000)}万\r\n`;
        }
        if (lackText !== "") {
            cm.sendOk(lackText);
            cm.dispose();
            return;
        }

        let confirm = "#e确认升级#n\r\n";
        confirm += `当前戒指：#v${selectRingId}##t${selectRingId}#\r\n`;
        confirm += `升级成功：#v${nextId}##t${nextId}#\r\n\r\n`;
        confirm += `本次成功率：${(nowRate * 100).toFixed(0)}%\r\n\r\n`;
        if (isFirstUpgrade) {
            confirm += `消耗道具：#v${FIRST_MATERIAL_ID}##t${FIRST_MATERIAL_ID}# × ${FIRST_MATERIAL_NUM}\r\n`;
        }
        confirm += `消耗道具：#v${UPGRADE_MATERIAL_ID}##t${UPGRADE_MATERIAL_ID}# × ${materialNum}\r\n`;
        confirm += `消耗金币：${金币图标} ${upgradeCost / 10000}万 (持有${Math.floor(haveGold / 10000)}万)\r\n\r\n`;
        confirm += "是否确认升级？";
        cm.sendYesNo(confirm);
    } else if (status === 2) {
        doUpgrade();
        cm.dispose();
    } else {
        cm.dispose();
    }
}

function countAllSkyLordRings() {
    let count = 0;
    let equipInv = cm.getInventory(1);
    let maxSlot = equipInv.getSlotLimit();
    for (let slot = 1; slot <= maxSlot; slot++) {
        let item = equipInv.getItem(slot);
        if (item != null && isSkyLordRing(item.getItemId())) count++;
    }

    let equippedInv = cm.getInventory(-1);
    for (let slot = -1; slot >= -199; slot--) {
        let item = equippedInv.getItem(slot);
        if (item != null && isSkyLordRing(item.getItemId())) count++;
    }
    return count;
}

function isSkyLordRing(itemId) {
    return itemId >= RING_START_ID && itemId <= RING_MAX_ID;
}

function scanAllRing() {
    ringCache = [];
    let inv = cm.getInventory(1);
    let maxSlot = inv.getSlotLimit();
    let hasSkyLordRing = countAllSkyLordRings() > 0;
    for (let slot = 1; slot <= maxSlot; slot++) {
        let item = inv.getItem(slot);
        if (item == null) continue;
        let itemId = item.getItemId();
        if ((!hasSkyLordRing && itemId === BASE_RING_ID) || isSkyLordRing(itemId)) {
            ringCache.push({ slot: slot, id: itemId });
        }
    }
}

function doUpgrade() {
    let inv = cm.getInventory(1);
    let oldItem = inv.getItem(selectSlot);
    if (oldItem == null || oldItem.getItemId() !== selectRingId) {
        cm.sendOk("操作失败，戒指已被移动！");
        return;
    }
    if (isSkyLordRing(selectRingId) && countAllSkyLordRings() !== 1) {
        cm.sendOk("角色必须且只能拥有1个苍穹霸主戒才能升级！");
        return;
    }
    if (selectRingId === BASE_RING_ID && countAllSkyLordRings() !== 0) {
        cm.sendOk("角色已经拥有苍穹霸主戒，无法再次升级第一级。");
        return;
    }

    let newRingId = selectRingId + 1;
    if (newRingId > RING_MAX_ID) {
        cm.sendOk("该戒指已是最高阶，无法继续升级！");
        return;
    }

    let targetLevel = newRingId - RING_START_ID + 1;
    let materialNum = targetLevel * MATERIAL_PER_LEVEL;
    let isFirstUpgrade = selectRingId === BASE_RING_ID;
    let upgradeCost = isFirstUpgrade ? FIRST_UPGRADE_COST : NORMAL_UPGRADE_COST;
    let nowRate = isFirstUpgrade ? FIRST_UPGRADE_RATE : NORMAL_UPGRADE_RATE;

    if (isFirstUpgrade && cm.getItemQuantity(FIRST_MATERIAL_ID) < FIRST_MATERIAL_NUM) {
        cm.sendOk("第一级升级材料不足！");
        return;
    }
    if (cm.getItemQuantity(UPGRADE_MATERIAL_ID) < materialNum || cm.getMeso() < upgradeCost) {
        cm.sendOk("升级材料或金币不足！");
        return;
    }

    if (isFirstUpgrade) cm.gainItem(FIRST_MATERIAL_ID, -FIRST_MATERIAL_NUM);
    cm.gainItem(UPGRADE_MATERIAL_ID, -materialNum);
    cm.gainMeso(-upgradeCost);

    let success = Math.random() < nowRate;
    let player = cm.getPlayer();
    let oldName = ItemInformationProvider.getInstance().getName(selectRingId);
    if (!success) {
        cm.sendOk("升级失败！");
        let failNotice = `玩家【${player.getName()}】升级【${oldName}】失败！`;
        player.sendAllWordNoticeNew(3, "苍穹霸主戒升级", failNotice);
        sendServerMsg(failNotice);
        player.dropMessage(6, failNotice);
        return;
    }

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

    InventoryManipulator.removeFromSlot(cm.getClient(), InventoryType.EQUIP, selectSlot, 1, false);
    player.gainEquip(
        newRingId,
        str, dex, int, luk,
        0, 0,
        watk, matk,
        hp, mp, wdef, mdef, acc, avoid,
        speed, jump, -1
    );

    let newName = ItemInformationProvider.getInstance().getName(newRingId);
    cm.sendOk(`升级成功！获得【#v${newRingId}##t${newRingId}#】\r\n四维+5、物攻+5、魔攻+10`);
    let successNotice = `恭喜玩家【${player.getName()}】将【${oldName}】升级为【${newName}】，四维+5、物攻+5、魔攻+10！`;
    player.sendAllWordNoticeNew(2, "苍穹霸主戒升级", successNotice);
    sendServerMsg(successNotice);
    player.dropMessage(6, successNotice);
}

function sendServerMsg(text) {
    cm.getPlayer().sendFullServerBroadcast("[苍穹霸主戒升级] " + text);
}
