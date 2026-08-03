/**
 * @description 物品仓库系统脚本
 */
var status = 0;
var text;
var selects; // 记录选中的物品索引
var inventoryType; // 0:水晶宝石 1:母矿 2:10%卷轴 3:60%卷轴 4:各种币 5高级卷轴
var actionType; // 0:存储 1:取出
var currentItemId; // 当前操作的物品ID
var batchStoreItems = []; // 批量存储的物品列表
var itemList; // 当前选中分类的物品列表

// 水晶宝石列表 (type=0)
var itemlist0 = [
    4005000, 4005001, 4005002, 4005003, 4005004,
    4021000, 4021001, 4021002, 4021003, 4021004,
    4021005, 4021006, 4021007, 4021008,
    4011006, 4011005, 4011004, 4011003, 4011002, 4011001, 4011000,
    4011007, 4021009, 4011008
];

// 母矿列表 (type=1)
var itemlist1 = [
    4004000, 4004001, 4004002, 4004003, 4004004,
    4010000, 4010001, 4010002, 4010003, 4010004,
    4010005, 4010006,
    4020000, 4020001, 4020002, 4020003, 4020004,
    4020005, 4020006, 4020007, 4020008, 4010007
];
// 10%成功率卷轴ID数组(type=2)
const itemlist2 = [
    2040915, // 盾牌攻击
    2043002, // 单手剑攻击
    2043012,
    2043102, // 单手斧攻击
    2043107,
    2043202, // 单手钝器
    2043207,
    2043302, // 短剑攻击
    2043307,
    2044002, // 双手剑攻击
    2044007,
    2044102, // 双手斧攻击
    2044107,
    2044202, // 双手钝器攻击
    2044207,
    2044302, // 抢攻击
    2044307,
    2044402, // 矛攻击
    2044407,
    2044502, // 弓攻击
    2044507,
    2044602, // 弩攻击
    2044607,
    2044702, // 拳套攻击
    2044707,
    2044802, // 拳甲攻击
    2044812,
    2044902, // 短枪攻击
    2044907,
    2043802, // 长杖魔力
    2043807,
    2043702, // 短杖魔力
    2043707,
    // 2040002, // 10%头盔防御卷轴
    // 2040005, // 10%头盔体力卷轴
    2040026, // 10%头盔智力卷轴
    2040031, // 10%头盔敏捷卷轴
    2040044,
    2040805, // 10%手套攻击卷轴
    2040822,
    2040830,
    2040816, // 10%手套魔力卷轴
    2040702, // 10%鞋子敏捷卷轴
    // 2040705, // 10%鞋子跳跃卷轴
    // 2040708, // 10%鞋子速度卷轴
    // 2041002, // 10%披风魔防卷轴
    // 2041005, // 10%披风防御卷轴
    // 2041008, // 10%披风体力卷轴
    2041014, // 10%披风力量卷轴
    2041017, // 10%披风智力卷轴
    2041020, // 10%披风敏捷卷轴
    2041023, // 10%披风运气卷轴
    2040412, // 10%上衣运气卷轴
    2040436,
    2040419, // 10%上衣力量卷轴
    2040432,
    // 2040402, // 10%上衣防御卷轴
    // 2040422, // 10%上衣体力卷轴
    2040612, // 10%裤裙敏捷卷轴
    2040636,
    // 2040619, // 10%裤裙跳跃卷轴
    // 2040622, // 10%裤裙体力卷轴
    2040502, // 10%全身铠甲敏捷卷轴
    2040523,
    // 2040505, // 10%全身铠甲防御卷轴
    2040514, // 10%全身铠甲智力卷轴
    2040527,
    2040517, // 10%全身铠甲运气卷轴
    // 2040302, // 10%耳环智力卷轴
    2040318, // 10%耳环敏捷卷轴
    2040335,
    2040323, // 10%耳环运气卷轴
    2040338,
    2040330, // 10%耳环智力卷轴
    2040314,
    2040303,
    // 2040328, // 10%耳环体力卷轴
    2041302, //腰带
    2041305,
    2041308,
    2041311,
];

// 60%成功率卷轴ID数组(type=3)
const itemlist3 = [
    2040914, // 盾牌攻击
    2043001, // 单手剑攻击
    2043011,
    2043101, // 单手斧攻击
    2043106,
    2043117,
    2043201, // 单手钝器攻击
    2043206,
    2043206,
    2043301, // 短剑攻击
    2043306,
    2044001, // 双手剑攻击
    2044006,
    2044025,
    2044101, // 双手斧攻击
    2044106,
    2044117,
    2044201, // 双手钝器攻击
    2044206,
    2044217,
    2044301, // 枪攻击
    2044306,
    2044317,
    2044401, // 矛攻击
    2044406,
    2044417,
    2044501, // 弓攻击
    2044506,
    2044512,
    2044601, // 弩攻击
    2044606,
    2044612,
    2044701, // 拳套攻击
    2044706,
    2044801, // 拳甲攻击
    2044811,
    2044712,
    2044901, // 短枪攻击
    2044906,
    2044908,
    2043801, // 长杖魔力
    2043806,
    2043701, // 短杖魔力
    2043706,
    2040001, // 10%头盔防御卷轴
    2040004, // 10%头盔体力卷轴
    2040025, // 10%头盔智力卷轴
    2040029, // 10%头盔敏捷卷轴
    2040804, // 10%手套攻击卷轴
    2040821,
    2040817, // 10%手套魔力卷轴
    2040701, // 10%鞋子敏捷卷轴
    2040704, // 10%鞋子跳跃卷轴
    2040707, // 10%鞋子速度卷轴
    // 2041001, // 10%披风魔防卷轴
    // 2041004, // 10%披风防御卷轴
    // 2041007, // 10%披风体力卷轴
    2041013, // 10%披风力量卷轴
    2041016, // 10%披风智力卷轴
    2041019, // 10%披风敏捷卷轴
    2041022, // 10%披风运气卷轴
    2040413, // 10%上衣运气卷轴
    2040435,
    2040425, // 10%上衣运气卷轴
    2040431,
    2040418, // 10%上衣力量卷轴
    2040401, // 10%上衣防御卷轴
    2040421, // 10%上衣体力卷轴
    2040613, // 10%裤裙敏捷卷轴
    2040635,
    2040618, // 10%裤裙跳跃卷轴
    2040621, // 10%裤裙体力卷轴
    2040501, // 10%全身铠甲敏捷卷轴
    2040522,
    2040538,
    2040504, // 10%全身铠甲防御卷轴
    2040513, // 10%全身铠甲智力卷轴
    2040526,
    2040516, // 10%全身铠甲运气卷轴
    2040301, // 10%耳环智力卷轴
    2040313,
    2040317, // 10%耳环敏捷卷轴
    2040321, // 10%耳环装饰运气卷轴
    2040337,
    2040326, // 10%耳环体力卷轴
    2040101, // 10%脸部装饰生命卷轴
    2040106, // 10%脸部装饰回避率卷轴
    2041300,//腰带
    2041301,
    2041303,
    2041304,
    2041306,
    2041307,
    2041309,
    2041310,
];
//高级卷轴
const itemlist5 = [
    //特殊
    2340000,
    2049115,
    2049100,
    //100%卷
    2043003,
    2043103,
    2043203,
    2043303,
    2043703,
    2043812,
    2044003,
    2044103,
    2044203,
    2044403,
    2044503,
    2044603,
    2044703,
    2040334,
    2040333,
    2040506,
    2040758,
    2040759,
    2040760,
    2040834,
    2040807,
    //50%
    2043022,
    2043120,
    2043220,
    2043313,
    2043713,
    2043813,
    2044028,
    2044120,
    2044220,
    2044303,
    2044320,
    2044420,
    2044513,
    2044613,
    2044713,
    2044817,
    2044910,
    2048010,
    2048011,
    2048012,
    2048013,
    2040205,
    2040206,
    2040207,
    2040100, // 10%脸部装饰生命卷轴
    2040105, // 10%脸部装饰回避率卷轴
    2040542,
    2041100,
    2041101,
    2041102,
    2041103,
    2041104,
    2041105,
    2041106,
    2041107,
    2041108,
    2041109,
    2041110,
    2041111,
];

// 各种币列表(type=4)
var itemlist4 = [
    4001129, 4001254
];

function start() {
    status = -1;
    try {
        action(1, 0, 0);
    } catch (e) {
        cm.dispose();
        // 打印错误日志便于调试
        console.error("物品仓库系统异常：", e);
    }
}

function action(mode, type, selection) {
    // console.info("物品仓库系统异常：status=" + status + "   mode=" + mode + "  type=" + type + "  selection=" + selection);
    if (mode === 1) {
        status++;
    } else {
        cm.dispose();
        return;
    }
    if (status == -1) {
        cm.dispose();
        return;
    }
    // 主菜单
    if (status == 0) {
        text = "                                 #k物品仓库系统#k#n\r\n";
        text += "\r\n";
        text += "#L0#成品矿石仓库#l\t\t\t\t\t #L1#母矿仓库#l\r\n";
        text += "\r\n";
        text += "#L2#10%成功率卷轴仓库#l\t\t #L3#60%成功率卷轴仓库#l\r\n";
        text += "\r\n";
        text += "#L5#高级卷轴#l\t\t \r\n";
        text += "\r\n";
        text += "#L6##r一键存储所有矿石#l\t\t\t #L8##r一键取出所有矿石#l\r\n";
        text += "#L7##r一键存储所有卷轴#l\r\n";
        cm.sendSimple(text);
    } else if (status == 1) {// 物品管理列表（各类物品）
        // 处理一键存储操作
        if (selection == 6) {
            prepareBatchStoreAllItem(); // 一键存储所有矿石（0+1）
            return;
        } else if (selection == 7) {
            prepareBatchStoreAllScroll(); // 一键存储所有卷轴（2+3）
            return;
        } else if (selection == 8) {
            cm.sendYesNo("#r注意背包位置，不够位置丢了不关我事哦！#k\r\n\r\n确定要一键取出所有矿石吗？");
            status = 4;
            return;
        }

        // 确定物品类型（0-4）
        inventoryType = selection;
        itemList = getCurrentItemList(inventoryType);
        const title = getTitleByType(inventoryType);

        text = `#d【${title}】#n\r\n`;
        text += "#k每个物品可进行存储或取出操作#n\r\n\r\n";

        itemList.forEach((itemId, i) => {
            const bagCount = cm.getPlayer().getItemQuantity(itemId, false);
            const storeCount = cm.getPlayer().getExtraStorage().getItemQuantity(itemId, inventoryType);

            text += `#b#n#v${itemId}# #z${itemId}# `;
            text += `#b#n[背包: #r#n${bagCount}] `;
            text += `#b#n[仓库: #r#n${storeCount}]#b#n\r\n`;
            if (itemId != 2340000 && itemId != 2049115 && itemId != 2049100) {
                text += `  #L${i * 2}##b存储#l          `;
            }
            text += `#L${i * 2 + 1}##b取出#l\r\n\r\n`;
        });

        cm.sendSimple(text);
    } else if (status == 2) { // 处理存储/取出操作（跳转数量输入）
        // **修复点2：增加参数有效性检查**
        if (!itemList || !itemList.length || selection === -1) {
            cm.sendOk("操作无效，请返回主菜单重试。");
            cm.dispose();
            return;
        }

        selects = Math.floor(selection / 2);
        actionType = selection % 2; // 0:存储 1:取出
        currentItemId = itemList[selects];

        const itemName = `#v${currentItemId}# #z${currentItemId}#`;
        const actionName = actionType === 0 ? "存储" : "取出";

        let maxCount, currentCount;
        if (actionType === 0) {
            currentCount = cm.getPlayer().getItemQuantity(currentItemId, false);
            const storeCount = cm.getPlayer().getExtraStorage().getItemQuantity(currentItemId, inventoryType);
            maxCount = Math.min(currentCount, 30000 - storeCount);
        } else {
            currentCount = cm.getPlayer().getExtraStorage().getItemQuantity(currentItemId, inventoryType);
            maxCount = currentCount;
        }

        if (maxCount <= 0) {
            const msg = actionType === 0
                ? "背包中没有可存储的该物品或仓库已满！"
                : "仓库中没有可取出的该物品！";
            cm.sendOk(msg);
            cm.dispose();
            return;
        }

        text = `请输入${actionName}数量：\r\n\r\n`;
        text += `${itemName}\r\n`;
        text += `#b#n当前${actionType === 0 ? "背包" : "仓库"}数量#r#e: ${currentCount}#b#n\r\n`;
        if (actionType === 0) {
            text += `可${actionName}上限: ${maxCount}\r\n`;
        }
        text += `\r\n请输入1-${maxCount}之间的数量：`;
        cm.sendGetNumber(text, maxCount, 1, maxCount);
    }
    // 执行存储/取出操作
    else if (status == 3) {
        const quantity = selection;
        if (quantity <= 0) {
            cm.sendOk("请输入有效的数量！");
            cm.dispose();
            return;
        }

        const actionName = actionType === 0 ? "存储" : "取出";
        let success, resultMsg;
        const player = cm.getPlayer();

        if (actionType === 0) {
            success = player.storeExtraItem(currentItemId, quantity, inventoryType);
            const newStoreCount = player.getExtraStorage().getItemQuantity(currentItemId, inventoryType);
            resultMsg = success
                ? `成功${actionName} #z${currentItemId}# x ${quantity}\r\n当前仓库中共有: ${newStoreCount}`
                : `${actionName}失败，请检查背包数量或仓库容量！`;
        } else {
            success = player.takeOutExtraItem(currentItemId, quantity, inventoryType);
            const newBagCount = player.getItemQuantity(currentItemId, false);
            resultMsg = success
                ? `成功${actionName} #z${currentItemId}# x ${quantity}\r\n当前背包中共有: ${newBagCount}`
                : `${actionName}失败，请检查仓库数量或背包空间！`;
        }
        cm.sendOk(resultMsg);
        cm.dispose();
    }
    // 批量存储确认 (使用 status=4 以避免与普通操作冲突)
    else if (status == 4) {
        if (batchStoreItems.length === 0) {
            cm.sendOk("没有可存储的物品。");
            cm.dispose();
            return;
        }

        let successCount = 0;
        let resultText = "一键存储结果：\r\n\r\n";
        const player = cm.getPlayer();

        // 遍历所有待存储物品
        batchStoreItems.forEach(item => {
            if (player.storeExtraItem(item.itemId, item.quantity, item.type)) {
                resultText += `#v${item.itemId}# #z${item.itemId}# 成功存储 ${item.quantity} 个\r\n`;
                successCount++;
            } else {
                resultText += `#v${item.itemId}# #z${item.itemId}# 存储失败\r\n`;
            }
        });

        resultText += `\r\n共处理${batchStoreItems.length}种物品，成功${successCount}种。`;
        cm.sendOk(resultText);
        cm.dispose();
    }
    // 确认后一键取出所有矿石
    else if (status == 5) {
        takeOutAllItem();
    }
    // 所有其他情况都直接关闭对话框
    else {
        cm.dispose();
    }
}

// 工具函数：根据类型获取物品列表
function getCurrentItemList(type) {
    switch (type) {
        case 0:
            return itemlist0;
        case 1:
            return itemlist1;
        case 2:
            return itemlist2;
        case 3:
            return itemlist3;
        case 4:
            return itemlist4;
        case 5:
            return itemlist5;
        default:
            return [];
    }
}

// 工具函数：根据类型获取标题
function getTitleByType(type) {
    const titles = [
        "成品矿石仓库",
        "母矿仓库",
        "10%成功率卷轴仓库",
        "60%成功率卷轴仓库",
        "各种币仓库",
        "高级卷轴",
    ];
    return titles[type] || "物品仓库";
}

// 准备一键存储所有矿石（type0和type1）
function prepareBatchStoreAllItem() {
    batchStoreItems = [];
    let text = "以下是可存储的矿石列表，请确认是否存储：\r\n\r\n";
    const storage = cm.getPlayer().getExtraStorage();
    const player = cm.getPlayer();

    // 处理水晶宝石（type=0）
    itemlist0.forEach(itemId => {
        const bagCount = player.getItemQuantity(itemId, false);
        if (bagCount <= 0) return;

        const storeCount = storage.getItemQuantity(itemId, 0);
        const maxStore = 30000 - storeCount;
        const realStore = Math.min(bagCount, maxStore);

        if (realStore > 0) {
            batchStoreItems.push({itemId, quantity: realStore, type: 0});
            text += `#v${itemId}# #z${itemId}# x ${realStore}\r\n`;
        }
    });

    // 处理母矿（type=1）
    let hasOre = false;
    itemlist1.forEach(itemId => {
        const bagCount = player.getItemQuantity(itemId, false);
        if (bagCount <= 0) return;

        const storeCount = storage.getItemQuantity(itemId, 1);
        const maxStore = 30000 - storeCount;
        const realStore = Math.min(bagCount, maxStore);

        if (realStore > 0) {
            if (!hasOre) {
                text += "\r\n"; // 与宝石列表空一行
                hasOre = true;
            }
            batchStoreItems.push({itemId, quantity: realStore, type: 1});
            text += `#v${itemId}# #z${itemId}# x ${realStore}\r\n`;
        }
    });

    if (batchStoreItems.length === 0) {
        cm.sendOk("没有可存储的矿石，背包中可能没有矿石或仓库已满！");
        cm.dispose();
    } else {
        text += `\r\n共${batchStoreItems.length}种矿石可存储，是否确认？`;
        cm.sendYesNo(text);
        // **修复点3：明确设置下一个状态为a=4，用于处理确认**
        status = 3;
    }
}

// 一键取出所有矿石（type0和type1）
function takeOutAllItem() {
    const player = cm.getPlayer();
    const storage = player.getExtraStorage();
    const batchTakeOutItems = [];

    [itemlist0, itemlist1].forEach((items, type) => {
        items.forEach(itemId => {
            const quantity = storage.getItemQuantity(itemId, type);
            if (quantity > 0) {
                batchTakeOutItems.push({itemId, quantity, type});
            }
        });
    });

    if (batchTakeOutItems.length === 0) {
        cm.sendOk("仓库中没有可取出的矿石！");
        cm.dispose();
        return;
    }

    let successCount = 0;
    let resultText = "一键取出结果：\r\n\r\n";
    batchTakeOutItems.forEach(item => {
        if (player.takeOutExtraItem(item.itemId, item.quantity, item.type)) {
            resultText += `#v${item.itemId}# #z${item.itemId}# 成功取出 ${item.quantity} 个\r\n`;
            successCount++;
        } else {
            resultText += `#v${item.itemId}# #z${item.itemId}# 取出失败\r\n`;
        }
    });

    resultText += `\r\n共处理${batchTakeOutItems.length}种矿石，成功${successCount}种。`;
    cm.sendOk(resultText);
    cm.dispose();
}

// 准备一键存储所有卷轴（type2和type3）
function prepareBatchStoreAllScroll() {
    batchStoreItems = [];
    let text = "以下是可存储的卷轴列表，请确认是否存储：\r\n\r\n";
    const storage = cm.getPlayer().getExtraStorage();
    const player = cm.getPlayer();

    // 处理10%卷轴（type=2）
    itemlist2.forEach(itemId => {
        const bagCount = player.getItemQuantity(itemId, false);
        if (bagCount <= 0) return;

        const storeCount = storage.getItemQuantity(itemId, 2);
        const maxStore = 30000 - storeCount;
        const realStore = Math.min(bagCount, maxStore);

        if (realStore > 0) {
            batchStoreItems.push({itemId, quantity: realStore, type: 2});
            text += `#v${itemId}# #z${itemId}# x ${realStore}\r\n`;
        }
    });

    // 处理60%卷轴（type=3）
    let has60 = false;
    itemlist3.forEach(itemId => {
        const bagCount = player.getItemQuantity(itemId, false);
        if (bagCount <= 0) return;

        const storeCount = storage.getItemQuantity(itemId, 3);
        const maxStore = 30000 - storeCount;
        const realStore = Math.min(bagCount, maxStore);

        if (realStore > 0) {
            if (!has60) {
                text += "\r\n"; // 与10%卷轴列表空一行
                has60 = true;
            }
            batchStoreItems.push({itemId, quantity: realStore, type: 3});
            text += `#v${itemId}# #z${itemId}# x ${realStore}\r\n`;
        }
    });

    // 处理高级卷轴（type=5）
    let hasAdvancedScroll = false;
    itemlist5.forEach(itemId => {
        if (itemId === 2340000 || itemId === 2049115 || itemId === 2049100) {
            return;
        }
        const bagCount = player.getItemQuantity(itemId, false);
        if (bagCount <= 0) return;

        const storeCount = storage.getItemQuantity(itemId, 5);
        const maxStore = 30000 - storeCount;
        const realStore = Math.min(bagCount, maxStore);

        if (realStore > 0) {
            if (!hasAdvancedScroll) {
                text += "\r\n"; // 与60%卷轴列表空一行
                hasAdvancedScroll = true;
            }
            batchStoreItems.push({itemId, quantity: realStore, type: 5});
            text += `#v${itemId}# #z${itemId}# x ${realStore}\r\n`;
        }
    });

    if (batchStoreItems.length === 0) {
        cm.sendOk("没有可存储的卷轴，背包中可能没有卷轴或仓库已满！");
        cm.dispose();
    } else {
        text += `\r\n共${batchStoreItems.length}种卷轴可存储，是否确认？`;
        cm.sendYesNo(text);
        // **修复点4：明确设置下一个状态为a=4，用于处理确认**
        status = 3;
    }
}
