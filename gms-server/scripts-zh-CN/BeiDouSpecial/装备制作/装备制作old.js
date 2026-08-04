/**
 * @description 副本相关制作
 * 9400263 杯尔加莫特  	NPC 9120027   爆 闪耀币 4001254
 * 9400270 杜纳斯	  	NPC 9120031   爆 4039015
 * 9400271 战舰 尼贝隆	NPC 9120039	  爆 4039019
 * 9400266 努克斯	    NPC 9120036	  爆 4039016
 * 9400294 再生杜纳斯  	NPC 9120047	  爆 4039018
 * 9400288 欧比啦	  	NPC 9120053	  爆 4039017
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[装备制作]#k系统#n\t\t\t\t\r\n";
var status = -1;
var i = 0;
var meso_id = 9999999;//金币
var cash_id = 9999998;//点卷
var 金币_icon = "#fUI/UIWindow.img/QuestIcon/7/0#";
var 选择的制作列表;
var 制作目标;
var isDebug = false;          // 调试模式开关
var goldScale = 10000;
var broadcastDefaultType = 1;
let selectedIndex = -1;       // 选中的索引
let 需要并被继承的装备 = null;      // 材料装备
//4251200 4251201 4251202

function isNeedEquip(id) {
    return id == 1004637 || id == 1112494 || //头盔
        id == 1032060 || id == 1032061 || id == 1032101 ||//耳环
        id == 1022118 || id == 1022123 || id == 1022129 ||//眼睛
        id == 1072344 || id == 1072732 || id == 1072737 || id == 1072743;//鞋子
}

var 耳环 = [
    //耳环奖励
    {
        id: 1032060,
        tipType: 6,
        needItems: [
            {id: 4001198, qty: 2, tip: "（毒物森林副本获取）"},//阿尔泰碎片
            {id: meso_id, qty: 1000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1032061,
        tipType: 6,
        needItems: [
            {id: 4001198, qty: 3, tip: "（毒物森林副本获取）"},
            {id: 1032060, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 20000},
        ]
    },
    //闪耀的阿尔泰
    {
        id: 1032101,
        tipType: 3,
        needItems: [
            {id: 4001198, qty: 4, tip: "（毒物森林副本获取）"},
            {id: 1032061, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 3000},
            {id: cash_id, qty: 30000},
        ]
    },
];

var 眼睛 = [
    //眼睛奖励
    {
        id: 1022118,
        tipType: 6,
        needItems: [
            {id: 4001246, qty: 2, tip: "（玩具副本获取）"},//温暖的阳光
            {id: meso_id, qty: 1000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1022123,
        tipType: 6,
        needItems: [
            {id: 4001246, qty: 3, tip: "（玩具副本获取）"},
            {id: 1022118, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 20000},
        ]
    },
    //精灵眼睛
    {
        id: 1022129,
        tipType: 3,
        needItems: [
            {id: 4001246, qty: 4, tip: "（玩具副本获取）"},
            {id: 1022123, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 3000},
            {id: cash_id, qty: 50000},
        ]
    },
];

var 鞋子 = [
    //黄丁鞋
    {
        id: 1072239,
        tipType: 6,
        needItems: [
            {id: 4032266, qty: 2, tip: "（海盗副本获取）"},
            {id: meso_id, qty: 2000},
            {id: cash_id, qty: 10000},
        ]
    },
    {
        id: 1072344,
        tipType: 3,
        needItems: [
            {id: 4032266, qty: 5, tip: "（海盗副本获取）"},
            {id: 1072239, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 5000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1072732,
        tipType: 3,
        needItems: [
            {id: 4039015, qty: 1, tip: "（杜纳斯产出）"},
            {id: 1072344, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 10000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1072737,
        tipType: 3,
        needItems: [
            {id: 4039016, qty: 1, tip: "（努克斯产出）"},
            {id: 1072732, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 20000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1072743,
        tipType: 3,
        needItems: [
            {id: 4039017, qty: 1, tip: "（欧比啦产出）"},
            {id: 1072737, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: meso_id, qty: 30000},
            {id: cash_id, qty: 50000},
        ]
    },
];

var 帽子 = [
    //愤怒扎昆头盔
    {
        id: 1004637,
        tipType: 3,
        needItems: [
            {id: 1002357, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1002390, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1002430, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003112, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003439, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1003854, qty: 1, tip: "（扎昆副本产出）"},
            {id: 1004119, qty: 1, tip: "（扎昆副本产出）"},
            {id: meso_id, qty: 10000},
            {id: cash_id, qty: 50000},
        ]
    },
    {
        id: 1003621,
        tipType: 3,
        needItems: [
            {id: 1004637, qty: 1, tip: "(继承该装备洗练和星级)"},
            {id: 1003450, qty: 1, tip: "（pb副本产出）"},
            {id: 4021010, qty: 50, tip: ""},
            {id: 4251202, qty: 1, tip: "（pb副本产出）"},
            {id: meso_id, qty: 30000},
            {id: cash_id, qty: 50000},
        ]
    }
];

function start() {
    action(1, 0, 0)
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        let text = OldTitle;
        text += " \r\n";
        text += "#b#L1#耳环#l\t\r\n\r\n";
        text += "#L2#眼睛#l\t\r\n\r\n";
        text += "#L3#鞋子#l\t\r\n\r\n";
        text += "#L4#帽子#l\t\r\n\r\n";
        text += "#L5#武器#l\t\r\n\r\n";
        text += "\r\n\r\n\t#r以下还未实现#k\t\r\n\r\n";
        text += "#L7#披风#l\t\r\n\r\n";
        text += "#L8#手套#l\t\r\n\r\n";
        text += "#L9#腰带#l\t\r\n\r\n";
        text += "#L10#项链#l\t\r\n\r\n";
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
        case 1:
            选择的制作列表 = 耳环;
            展示物品制作列表();
            break;
        case 2:
            选择的制作列表 = 眼睛;
            展示物品制作列表();
            break;
        case 3:
            选择的制作列表 = 鞋子;
            展示物品制作列表();
            break;
        case 4:
            选择的制作列表 = 帽子;
            展示物品制作列表();
            break;
        case 5:
            openNpc("装备制作/武器制作");
            break;
        default:
            cm.sendOk("#b瞎么？没看到上面上写的还未实现，你就等吧！");
            cm.dispose();
    }
}


function 展示物品制作列表() {
    //展示物品
    let text = OldTitle + "\r\n请选择要制作的物品：\r\n\r\n";
    选择的制作列表.forEach((item, index) => {
        // 拼接目标物品信息
        text += `#L${index}##b制作#v${item.id}#  #r#z${item.id}##k\r\n`;
        text += "\r\n";
    });
    cm.sendSimple(text);
}


function 确认制作(index) {
    selectedIndex = index; // 记录选中索引
    const targetItem = 选择的制作列表[index];
    制作目标 = targetItem;
    if (!targetItem) {
        cm.sendOk("无效的选择");
        cm.dispose();
        return;
    }
    // 构建确认信息
    let confirmText = `确定要制作 #i${targetItem.id}# #r#t${targetItem.id}# #k吗？\r\n#b所需材料：#k\r\n`;
    targetItem.needItems.forEach(need => {
        if (need.id === meso_id) {
            confirmText += `\r\n${金币_icon} x ${获取金币显示(need.qty)}\r\n`; // 使用金币图标
        } else if (need.id === cash_id) {
            confirmText += `#b点券 x #k ${need.qty}\r\n`; // 使用点券相关图标
        } else {
            // 仅当need.tip存在且不为空时才拼接提示部分
            const tipText = need.tip ? `\t#b${need.tip}#k` : '';
            confirmText += `#i${need.id}# #t${need.id}# x ${need.qty}${tipText}\r\n`;
        }
    });
    cm.sendYesNo(confirmText);
}


// function 制作物品() {
//     const targetItem = 制作目标;
//     if (!targetItem) {
//         cm.sendOk("制作信息已过期，请重新选择");
//         cm.dispose();
//         return;
//     }
//
//     // 检查背包是否能容纳目标物品
//     if (!cm.canHold(targetItem.id, 1)) {
//         cm.sendOk("背包空间不足，无法制作");
//         cm.dispose();
//         return;
//     }
//
//     // 检查所需材料
//     const lackItems = [];
//     let canExchange = true;
//
//     targetItem.needItems.forEach(need => {
//         if (need.id === meso_id) {
//             // 检查金币
//             if (cm.getMeso() < 获取金币(need.qty)) {
//                 lackItems.push(`金币（缺少：${获取金币(need.qty) - cm.getMeso()}）`);
//                 canExchange = false;
//             }
//         } else if (need.id === cash_id) {
//             // 检查点券（参考Cash.txt中点券相关处理）
//             if (cm.getPlayer().getCashShop().getCash(1) < need.qty) {
//                 lackItems.push(`点券（缺少：${need.qty - cm.getPlayer().getCashShop().getCash(1)}）`);
//                 canExchange = false;
//             }
//         } else {
//             // 检查普通物品
//             if (cm.getItemQuantity(need.id) < need.qty) {
//                 lackItems.push(`#t${need.id}#（缺少：${need.qty - cm.getItemQuantity(need.id)}）`);
//                 canExchange = false;
//             }
//         }
//     });
//
//     if (!canExchange) {
//         cm.sendOk(`材料不足：\r\n${lackItems.join("\r\n")}`);
//         cm.dispose();
//         return;
//     }
//
//     // 扣除所需材料
//     targetItem.needItems.forEach(need => {
//         if (need.id === meso_id) {
//             cm.gainMeso(-获取金币(need.qty));
//         } else if (need.id === cash_id) {
//             cm.getPlayer().getCashShop().gainCash(1, -need.qty);
//         } else {
//             cm.gainItem(need.id, -need.qty);
//         }
//     });
//
//     // 给予目标物品
//     cm.gainItem(targetItem.id, 1);
//     cm.sendOk(`恭喜您,制作 #i${targetItem.id}# #t${targetItem.id}# 成功！`);
//     const tipType = targetItem.tipType || 6;
//     sendSuperMegaphone(cm.getPlayer(), tipType, "装备制作", `恭喜玩家${cm.getPlayer().getName()}成功制作出【${cm.getPlayer().getItemName(targetItem.id)}】!`);
//     cm.dispose();
// }
//
// function 获取金币(meso) {
//     return meso * 10000;
// }
//
// function 获取金币显示(meso) {
//     if (meso >= 10000) {
//         return `${meso / 10000}E\r\n`;
//     } else {
//         return `${meso}W\r\n`;
//     }
// }

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}

/**
 * 执行物品制作逻辑
 */
function doCraftItem() {
    if (!制作目标) {
        cm.sendOk("制作信息已过期，请重新选择！");
        cm.dispose();
        return;
    }

    const player = cm.getPlayer();
    // 检查背包是否能容纳目标物品
    if (!cm.canHold(制作目标.id, 1)) {
        cm.sendOk("背包空间不足或者您已有同类物品，无法制作！");
        cm.dispose();
        return;
    }

    // 调试模式跳过材料检查
    if (!isDebug) {
        // 第一步：全量检查材料是否满足（不扣除）
        const lackItems = [];
        const canCraft = checkAllMaterials(player, lackItems);

        // 材料不足则提示并终止
        if (!canCraft) {
            cm.sendOk(`材料不足：\r\n${lackItems.join("\r\n")}`);
            cm.dispose();
            return;
        }

        // 第二步：所有材料满足，统一扣除
        deductAllMaterials(player);
    } else {
        // 调试模式：仅获取武器材料，不扣除
        制作目标.needItems.forEach(need => {
            if (selectedIndex > 0 && isNeedEquip(need.id)) {
                需要并被继承的装备 = player.getInventory(InventoryType.EQUIP).getItem(1);
            }
        });
    }
    获取新装备并继承属性(制作目标.id, 需要并被继承的装备)
    // 制作成功提示+广播
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

const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');

function 获取新装备并继承属性(targetId, needItem) {
    const player = cm.getPlayer();
    const newItem = cm.gainItem(targetId, 1);
    if (!newItem) {
        cm.sendOk("制作失败：无法生成目标物品！");
        cm.dispose();
        return;
    }
    newItem.setFlag(1); // 上锁
    // 武器属性继承逻辑
    if (needItem) {
        newItem.replaceData(needItem);
        // 移除原材料装备
        InventoryManipulator.removeFromSlot(
            player.getClient(),
            InventoryType.EQUIP,
            needItem.getPosition(),
            1,
            false
        );
    }
    player.forceUpdateItem(newItem); // 强制更新装备状态
}

/**
 * 全量检查所有材料是否满足（仅检查，不扣除）
 * @param {object} player - 玩家对象
 * @param {array} lackItems - 缺失材料列表（输出参数）
 * @returns {boolean} 是否所有材料都满足
 */
function checkAllMaterials(player, lackItems) {
    let allSatisfied = true;

    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            // 检查金币
            const needMeso = getMesoValue(need.qty);
            if (cm.getMeso() < needMeso) {
                lackItems.push(`金币（缺少：${needMeso - cm.getMeso()}）`);
                allSatisfied = false;
            }
        } else if (need.id === cash_id) {
            // 检查点券
            const cash = player.getCashShop().getCash(1);
            if (cash < need.qty) {
                lackItems.push(`点券（缺少：${need.qty - cash}）`);
                allSatisfied = false;
            }
        } else {
            // 检查普通物品/武器材料
            if (selectedIndex > 0 && isNeedEquip(need.id)) {
                需要并被继承的装备 = player.getInventory(InventoryType.EQUIP).getItem(1);
                if (!需要并被继承的装备 || 需要并被继承的装备.getItemId() !== need.id) {
                    lackItems.push(`#t${need.id}#必须放在装备栏第一格`);
                    allSatisfied = false;
                }
            } else {
                const haveQty = cm.getItemQuantity(need.id);
                if (haveQty < need.qty) {
                    lackItems.push(`#t${need.id}#（缺少：${need.qty - haveQty}）`);
                    allSatisfied = false;
                }
            }
        }
    });

    return allSatisfied;
}

/**
 * 统一扣除所有材料（仅在全量检查通过后调用）
 * @param {object} player - 玩家对象
 */
function deductAllMaterials(player) {
    制作目标.needItems.forEach(need => {
        if (need.id === meso_id) {
            // 扣除金币
            const needMeso = getMesoValue(need.qty);
            cm.gainMeso(-needMeso);
        } else if (need.id === cash_id) {
            // 扣除点券
            player.getCashShop().gainCash(1, -need.qty);
        } else {
            // 扣除普通物品（武器材料在属性继承时移除，此处无需处理）
            if (!(selectedIndex > 0 && isNeedEquip(need.id))) {
                cm.gainItem(need.id, -need.qty);
            }
        }
    });
}

/**
 * 计算金币实际值（换算成游戏内单位）
 * @param {number} meso - 配置中的金币数量
 * @returns {number} 实际金币值
 */
function getMesoValue(meso) {
    return meso * goldScale;
}

/**
 * 格式化金币显示（W/E单位）
 * @param {number} meso - 配置中的金币数量
 * @returns {string} 格式化后的显示文本（无小数）
 */
function 获取金币显示(meso) {
    const realMeso = getMesoValue(meso); // 假设该函数已存在，返回正确的金币数值
    if (realMeso >= 100000000) {
        // 除以1亿后取整（推荐用Math.floor向下取整，也可换Math.round四舍五入）
        return `${Math.floor(realMeso / 100000000)}E`;
    } else if (realMeso >= 10000) {
        // 除以1万后取整
        return `${Math.floor(realMeso / 10000)}W`;
    } else {
        return `${realMeso}`;
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
