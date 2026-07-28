/**
 * @description 项链制作
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[项链制作]#k系统#n\t\t\t\t\r\n";
var status = -1;
var meso_id = 9999999;//金币
var cash_id = 9999998;//点卷
var 金币_icon = "#fUI/UIWindow.img/QuestIcon/7/0#";
var goldScale = 10000;
var broadcastDefaultType = 1;

var 选择的制作列表;
var 制作目标;
var 需要并被继承的装备 = null;

var 项链 = [
    {
        id: 1122076,
        tipType: 6,
        needItems: [
            {id: 1122000, qty: 1, tip: ""},
            {id: 1122012, qty: 1, tip: ""},
            {id: 4021010, qty: 10, tip: ""},
            {id: meso_id, qty: 1000},
            {id: cash_id, qty: 6666},
        ]
    },
];

function start() {
    action(1, 0, 0)
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
        let text = OldTitle;
        text += " \r\n";
        text += "#L0#项链制作#l\t\r\n\r\n";
        text += "#L1#项链强化#l\t\r\n\r\n";
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else if (status === 2) {
        确认制作(selection);
    } else if (status === 3) {
        doCraftItem();
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        case 0:
            选择的制作列表 = 项链;
            展示物品制作列表();
            break;
        case 1:
            openNpc("装备制作/项链升级");
            break;
        default:
            cm.sendOk("该功能暂不支持，敬请期待！");
            cm.dispose();
    }
}

function 展示物品制作列表() {
    let text = OldTitle + "\r\n请选择要制作的物品：\r\n\r\n";
    选择的制作列表.forEach((item, index) => {
        text += `#L${index}##b制作#v${item.id}# #z${item.id}##k\r\n`;
        text += "\r\n";
    });
    cm.sendSimple(text);
}

function 确认制作(index) {
    const targetItem = 选择的制作列表[index];
    制作目标 = targetItem;
    if (!targetItem) {
        cm.sendOk("无效的选择");
        cm.dispose();
        return;
    }
    let confirmText = `确定要制作 #v${targetItem.id}# #r#z${targetItem.id}# #k吗？\r\n#b所需材料：#k\r\n`;
    targetItem.needItems.forEach(need => {
        if (need.id === meso_id) {
            confirmText += `\r\n${金币_icon} x ${获取金币显示(need.qty)}\r\n`;
        } else if (need.id === cash_id) {
            confirmText += `#b点券 x #k ${need.qty}\r\n`;
        } else {
            const tipText = need.tip ? `\t#b${need.tip}#k` : '';
            confirmText += `#i${need.id}# #t${need.id}# x ${need.qty}${tipText}\r\n`;
        }
    });
    cm.sendYesNo(confirmText);
}

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}

const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');

function doCraftItem() {
    if (!制作目标) {
        cm.sendOk("制作信息已过期，请重新选择！");
        cm.dispose();
        return;
    }

    const player = cm.getPlayer();
    if (!cm.canHold(制作目标.id, 1)) {
        cm.sendOk("背包空间不足或者您已有同类物品，无法制作！");
        cm.dispose();
        return;
    }

    const lackItems = [];
    const canCraft = checkAllMaterials(player, lackItems);

    if (!canCraft) {
        cm.sendOk(`材料不足：\r\n${lackItems.join("\r\n")}`);
        cm.dispose();
        return;
    }

    deductAllMaterials(player);
    获取新装备并继承属性(制作目标.id, 需要并被继承的装备);

    cm.sendOk(`恭喜您，制作 #i${制作目标.id}# #t${制作目标.id}# 成功！`);
    const tipType = 制作目标.tipType || broadcastDefaultType;
    const itemName = player.getItemName(制作目标.id);
    player.sendBroadcast(
        tipType,
        "装备制作",
        `恭喜玩家${player.getName()}成功制作出【${itemName}】!`,
        true
    );

    cm.dispose();
}

function 获取新装备并继承属性(targetId, needItem) {
    const player = cm.getPlayer();
    const newItem = cm.gainItem(targetId, 1);
    if (!newItem) {
        cm.sendOk("制作失败：无法生成目标物品！");
        cm.dispose();
        return;
    }
    newItem.setFlag(1);
    if (needItem) {
        newItem.replaceData(needItem);
        InventoryManipulator.removeFromSlot(
            player.getClient(),
            InventoryType.EQUIP,
            needItem.getPosition(),
            1,
            false
        );
    }
    player.forceUpdateItem(newItem);
}

function checkAllMaterials(player, lackItems) {
    let allSatisfied = true;

    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            const needMeso = getMesoValue(need.qty);
            if (cm.getMeso() < needMeso) {
                lackItems.push(`金币（缺少：${needMeso - cm.getMeso()}）`);
                allSatisfied = false;
            }
        } else if (need.id === cash_id) {
            const cash = player.getCashShop().getCash(1);
            if (cash < need.qty) {
                lackItems.push(`点券（缺少：${need.qty - cash}）`);
                allSatisfied = false;
            }
        } else {
            if (cm.getItemQuantity(need.id) < need.qty) {
                lackItems.push(`#t${need.id}#（缺少：${need.qty - cm.getItemQuantity(need.id)}）`);
                allSatisfied = false;
            }
        }
    });

    return allSatisfied;
}

function deductAllMaterials(player) {
    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            const needMeso = getMesoValue(need.qty);
            cm.gainMeso(-needMeso);
        } else if (need.id === cash_id) {
            player.getCashShop().gainCash(1, -need.qty);
        } else {
            cm.gainItem(need.id, -need.qty);
        }
    });
}

function getMesoValue(meso) {
    return meso * goldScale;
}

function 获取金币显示(meso) {
    const realMeso = getMesoValue(meso);
    if (realMeso >= 100000000) {
        return `${Math.floor(realMeso / 100000000)}E`;
    } else if (realMeso >= 10000) {
        return `${Math.floor(realMeso / 10000)}W`;
    } else {
        return `${realMeso}`;
    }
}