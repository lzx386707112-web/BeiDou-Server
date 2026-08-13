var status = -1;
var 可强化物品列表 = [1122076];
var 初始成功率 = 0.7;
var 每次成功率减少 = 0.05;
var 最低成功率 = 0.4;
var 每次强化属性增加值 = 30;
var 每种材料概率加成 = 0.01;
var 加成材料数量 = 100;
var 加成材料种类数 = 20;
var 启用材料加成等级 = 6;
var 零达标罚款 = 50000000;
var meso_id = 9999999;
var cash_id = 9999998;
var goldScale = 10000;
var needItems = [
    {id: 4021010, qty: 1},
    {id: meso_id, qty: 5000},
    {id: cash_id, qty: 6666},
];
var 本次材料等级 = -1;
var 本次等级材料 = [];

const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const CashShop = Java.type('org.gms.server.CashShop');
const DatabaseConnection = Java.type('org.gms.util.DatabaseConnection');
const MonsterInformationProvider = Java.type('org.gms.server.life.MonsterInformationProvider');
const ItemInformationProvider = Java.type('org.gms.server.ItemInformationProvider');

function start() {
    status = -1;
    try {
        action(1, 0, 0);
    } catch (e) {
        cm.dispose();
        console.error("项链升级脚本错误:", e);
    }
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
        main();
    } else if (status === 1) {
        if (selection === 0) {
            var equip = cm.getInventory(1).getItem(1);
            if (equip === null || !isInList(equip.getItemId())) {
                cm.sendOk("装备栏第一格的装备不符合强化条件！");
                cm.dispose();
            } else if ((equip.getExpandAttribute1() || 0) < 启用材料加成等级) {
                do强化();
            } else {
                提示等级材料(equip.getExpandAttribute1() || 0);
            }
        } else {
            cm.dispose();
        }
    } else if (status === 2) {
        if (selection === 0) {
            do强化();
        } else {
            cm.dispose();
        }
    } else {
        cm.dispose();
    }
}

function main() {
    var text = "\t\t\t\t\t#e#k欢迎来到#r[项链升级]#k系统#n\t\t\t\t\r\n";
    text += " \r\n";
    text += "【强化规则】\r\n";
    text += "1. 可强化道具：";
    for (var i = 0; i < 可强化物品列表.length; i++) {
        text += "#v" + 可强化物品列表[i] + "##t" + 可强化物品列表[i] + "#";
        if (i < 可强化物品列表.length - 1) {
            text += "、";
        }
    }
    text += "\r\n";
    text += "2. 每次强化成功：全属性+30\r\n";
    text += "3. 成功率：初始70%，每次强化减少5%，最低40%\r\n";
    text += "4. 强化失败：装备炸掉消失\r\n";
    text += "5. 强化装备必须放在装备栏第一格\r\n";
    text += "6. 6级起每级固定收集20种小怪掉落物，每达标1种增加1%成功率\r\n";
    text += "7. 强化需要消耗材料：\r\n";

    for (var i = 0; i < needItems.length; i++) {
        var item = needItems[i];
        var have;
        var itemDisplay;
        var itemQtyDisplay;
        var haveDisplay;
        if (item.id === meso_id) {
            have = cm.getPlayer().getMeso();
            itemDisplay = "金币";
            itemQtyDisplay = item.qty + "万";
            haveDisplay = Math.floor(have / goldScale) + "万";
        } else if (item.id === cash_id) {
            have = cm.getPlayer().getCashShop().getCash(CashShop.NX_CREDIT);
            itemDisplay = "点卷";
            itemQtyDisplay = item.qty.toString();
            haveDisplay = have.toString();
        } else {
            have = cm.getItemQuantity(item.id);
            itemDisplay = "#v" + item.id + "##t" + item.id + "#";
            itemQtyDisplay = item.qty.toString();
            haveDisplay = have.toString();
        }
        var color = have >= getRealValue(item) ? "#b" : "#r";
        text += "   " + color + itemDisplay + " x " + itemQtyDisplay + " (已有: " + haveDisplay + ")#k\r\n";
    }
    text += "\r\n";

    var equip = cm.getInventory(1).getItem(1);
    var can强化 = false;
    var message = "";

    if (equip === null) {
        message = "#r装备栏第一格没有装备！#k\r\n";
    } else if (!isInList(equip.getItemId())) {
        message = "#r装备栏第一格是#v" + equip.getItemId() + "##t" + equip.getItemId() + "#，不在可强化列表中！#k\r\n";
    } else {
        var currentLevel = equip.getExpandAttribute1() || 0;
        var currentRate = Math.max(最低成功率, 初始成功率 - (currentLevel * 每次成功率减少));
        message = "当前装备：#v" + equip.getItemId() + "##t" + equip.getItemId() + "#\r\n";
        message += "当前强化等级：" + currentLevel + "级\r\n";
        message += "本次成功率：" + (currentRate * 100).toFixed(0) + "%\r\n";

        if (checkMaterials()) {
            can强化 = true;
        } else {
            message += "#r材料不足！#k\r\n";
        }
    }

    text += message;

    if (can强化) {
        text += "\r\n#L0#开始强化项链#l\r\n\r\n";
        cm.sendSimple(text);
    } else {
        cm.sendOk(text);
    }
}

function getRealValue(item) {
    if (item.id === meso_id) {
        return item.qty * goldScale;
    }
    return item.qty;
}

function isInList(itemId) {
    for (var i = 0; i < 可强化物品列表.length; i++) {
        if (可强化物品列表[i] === itemId) {
            return true;
        }
    }
    return false;
}

function checkMaterials() {
    for (var i = 0; i < needItems.length; i++) {
        var item = needItems[i];
        if (item.id === meso_id) {
            if (cm.getPlayer().getMeso() < item.qty * goldScale) {
                return false;
            }
        } else if (item.id === cash_id) {
            if (cm.getPlayer().getCashShop().getCash(CashShop.NX_CREDIT) < item.qty) {
                return false;
            }
        } else {
            if (cm.getItemQuantity(item.id) < item.qty) {
                return false;
            }
        }
    }
    return true;
}

function consumeMaterials() {
    for (var i = 0; i < needItems.length; i++) {
        var item = needItems[i];
        if (item.id === meso_id) {
            cm.gainMeso(-item.qty * goldScale);
        } else if (item.id === cash_id) {
            cm.getPlayer().getCashShop().gainCash(CashShop.NX_CREDIT, -item.qty);
        } else {
            cm.gainItem(item.id, -item.qty);
        }
    }
}

function 获取小怪材料池() {
    var materials = [];
    var selectedItemIds = {};
    var selectedMonsterIds = {};
    var con = null;
    var ps = null;
    var rs = null;

    try {
        con = DatabaseConnection.getConnection();
        ps = con.prepareStatement(
            "SELECT DISTINCT itemid, dropperid FROM drop_data " +
            "WHERE itemid BETWEEN 4000000 AND 4009999 " +
            "AND questid = 0 AND chance > 0 " +
            "ORDER BY dropperid, itemid"
        );
        rs = ps.executeQuery();

        var monsterProvider = MonsterInformationProvider.getInstance();
        var itemProvider = ItemInformationProvider.getInstance();
        while (rs.next()) {
            var itemId = rs.getInt("itemid");
            var monsterId = rs.getInt("dropperid");
            if (selectedItemIds[itemId] || selectedMonsterIds[monsterId] || monsterProvider.isBoss(monsterId)) {
                continue;
            }
            var monsterName = monsterProvider.getMobNameFromId(monsterId);
            var itemName = itemProvider.getName(itemId);
            if (!monsterName || !itemName || itemName === "MISSINGNO" ||
                itemProvider.isQuestItem(itemId) || itemProvider.isPartyQuestItem(itemId)) {
                continue;
            }
            selectedItemIds[itemId] = true;
            selectedMonsterIds[monsterId] = true;
            materials.push({itemId: itemId, monsterId: monsterId});
        }
    } finally {
        if (rs !== null) {
            rs.close();
        }
        if (ps !== null) {
            ps.close();
        }
        if (con !== null) {
            con.close();
        }
    }

    return 固定洗牌(materials);
}

function 固定洗牌(materials) {
    var seed = 1122076;
    for (var i = materials.length - 1; i > 0; i--) {
        seed = (seed * 1664525 + 1013904223) >>> 0;
        var j = seed % (i + 1);
        var temp = materials[i];
        materials[i] = materials[j];
        materials[j] = temp;
    }
    return materials;
}

function 获取等级材料(currentLevel) {
    var pool = 获取小怪材料池();
    if (pool.length < 加成材料种类数) {
        return [];
    }

    var materials = [];
    var startIndex = ((currentLevel - 启用材料加成等级) * 加成材料种类数) % pool.length;
    for (var i = 0; i < 加成材料种类数; i++) {
        materials.push(pool[(startIndex + i) % pool.length]);
    }
    return materials;
}

function 提示等级材料(currentLevel) {
    var equip = cm.getInventory(1).getItem(1);
    if (equip === null || !isInList(equip.getItemId()) || (equip.getExpandAttribute1() || 0) !== currentLevel) {
        cm.sendOk("装备栏第一格的装备不符合强化条件！");
        cm.dispose();
        return;
    }

    本次材料等级 = currentLevel;
    本次等级材料 = 获取等级材料(currentLevel);
    if (本次等级材料.length !== 加成材料种类数) {
        cm.sendOk("当前可用的小怪掉落物不足 " + 加成材料种类数 + " 种，无法进行6级以上强化，请联系管理员。");
        cm.dispose();
        return;
    }

    var currentRate = Math.max(最低成功率, 初始成功率 - (currentLevel * 每次成功率减少));
    var completedCount = 获取达标材料().length;
    var bonusRate = Math.min(1, currentRate + completedCount * 每种材料概率加成);
    var text = "#e" + currentLevel + "级项链固定收集清单#n\r\n\r\n";
    text += "原成功率：#r" + (currentRate * 100).toFixed(0) + "%#k\r\n";
    text += "当前达标：#b" + completedCount + "/" + 加成材料种类数 + "种#k\r\n";
    text += "本次成功率：#b" + (bonusRate * 100).toFixed(0) + "%#k\r\n\r\n";
    text += "每种持有 " + 加成材料数量 + " 个即增加1%成功率，强化时只消耗达标材料：\r\n";

    for (var i = 0; i < 本次等级材料.length; i++) {
        var material = 本次等级材料[i];
        var itemId = material.itemId;
        var have = cm.getItemQuantity(itemId);
        var color = have >= 加成材料数量 ? "#b" : "#r";
        text += color + "#v" + itemId + "# " + have + "/" + 加成材料数量 + "#k\r\n";
    }

    text += "\r\n#L0##b按当前达标数量开始强化#l";
    cm.sendSimple(text);
}

function 获取达标材料() {
    var completed = [];
    for (var i = 0; i < 本次等级材料.length; i++) {
        if (cm.getItemQuantity(本次等级材料[i].itemId) >= 加成材料数量) {
            completed.push(本次等级材料[i]);
        }
    }
    return completed;
}

function consumeCompletedMaterials(completedMaterials) {
    for (var i = 0; i < completedMaterials.length; i++) {
        cm.gainItem(completedMaterials[i].itemId, -加成材料数量);
    }
}

function do强化() {
    var equip = cm.getInventory(1).getItem(1);

    if (equip === null || !isInList(equip.getItemId())) {
        cm.sendOk("装备栏第一格的装备不符合强化条件！");
        cm.dispose();
        return;
    }

    if (!checkMaterials()) {
        cm.sendOk("材料不足，无法强化！");
        cm.dispose();
        return;
    }

    var player = cm.getPlayer();
    var currentLevel = equip.getExpandAttribute1() || 0;
    var completedMaterials = [];
    if (currentLevel >= 启用材料加成等级) {
        if (本次材料等级 !== currentLevel || 本次等级材料.length !== 加成材料种类数) {
            cm.sendOk("强化等级或材料清单已经变化，请重新打开项链升级界面。");
            cm.dispose();
            return;
        }
        completedMaterials = 获取达标材料();
        if (completedMaterials.length === 0) {
            var fine = Math.min(player.getMeso(), 零达标罚款);
            if (fine > 0) {
                cm.gainMeso(-fine);
            }
            cm.sendOk("你伤害了我，还一笑而过，我代表月亮罚你5千万。");
            cm.dispose();
            return;
        }
    }

    consumeMaterials();
    consumeCompletedMaterials(completedMaterials);

    var currentRate = Math.max(最低成功率, 初始成功率 - (currentLevel * 每次成功率减少));
    currentRate = Math.min(1, currentRate + completedMaterials.length * 每种材料概率加成);
    var isSuccess = Math.random() < currentRate;

    if (isSuccess) {
        equip.setStr(equip.getStr() + 每次强化属性增加值);
        equip.setDex(equip.getDex() + 每次强化属性增加值);
        equip.setInt(equip.getInt() + 每次强化属性增加值);
        equip.setLuk(equip.getLuk() + 每次强化属性增加值);
        equip.setWatk(equip.getWatk() + 每次强化属性增加值);
        equip.setMatk(equip.getMatk() + 每次强化属性增加值);
        equip.setExpandAttribute1(currentLevel + 1);

        player.equipChanged();
        player.forceUpdateItem(equip);
        var itemName = cm.getPlayer().getItemName(equip.getItemId());
        var tip = `恭喜玩家【${player.getName()}】走了狗屎运，将【${itemName}】强化到${currentLevel + 1}级！`;
        cm.sendOk("恭喜！#v" + equip.getItemId() + "##t" + equip.getItemId() + "#强化成功！\r\n当前强化等级：" + (currentLevel + 1) + "级");
        sendSuperMegaphone(player, 2, "项链升级", tip);
        全服通告(tip);
    } else {
        var itemName = cm.getPlayer().getItemName(equip.getItemId());
        InventoryManipulator.removeFromSlot(cm.getClient(), InventoryType.EQUIP, 1, 1, true);
        cm.sendOk("很遗憾！" + itemName + "强化失败！\r\n失败后装备炸掉消失");
        var tip = `倒霉孩子【${player.getName()}】强化【${itemName}】到${currentLevel + 1}级失败！装备消失！`;
        sendSuperMegaphone(player, 3, "项链升级", tip);
        全服通告(tip);
    }
    cm.dispose();
}

function 全服通告(tip) {
    cm.getPlayer().sendFullServerBroadcast(tip);
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
