var status = -1;
var sel;
const Fishing = Java.type('org.gms.util.packets.Fishing');
const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const ItemId = Java.type('org.gms.constants.id.ItemId');

function start() {
    var text = "\t\t\t\t\t#e#k欢迎来到#r[钓鱼系统]#k系统#n\t\t\t\t\r\n\r\n";
    text += getFishInfo();
    text += "#b#L999#钓鱼说明#l\r\n\r\n";
    text += "#L0#进入钓鱼场#n#l\r\n\r\n";
    text += "#L1#500万购买钓鱼椅#n#l\r\n\r\n";
    text += "#L2#兑换公婆戒指#l\r\n\r\n";
    text += "#L3#鱼的兑换#l\r\n\r\n";
    text += "#L4#道具兑换#l\r\n\r\n";
    text += "#L5#查看钓鱼掉落#l\r\n\r\n";
    cm.sendSimple(text);
}

/**
 * 获取钓鱼等级与成功率信息
 * @returns {string} 格式化的钓鱼信息文本
 */
function getFishInfo() {
    // 1. 获取玩家钓鱼总经验，做容错处理（避免非数字/负数）
    let fishTotalExp = Number(cm.getPlayer().getFishLevel()) || 0;
    fishTotalExp = Math.max(fishTotalExp, 0); // 确保经验值非负

    // 2. 核心计算（语义化变量命名，逻辑清晰）
    const expPerLevel = 1000; // 每级所需经验（常量抽离，便于后续调整）
    const fishLevel = Math.floor(fishTotalExp / expPerLevel); // 钓鱼等级（取整数）
    const currentExp = fishTotalExp - (fishLevel * expPerLevel); // 当前等级剩余经验
    const successRateBonus = fishLevel * 1; // 每级加成1%成功率

    // 3. 格式化返回文本（排版更清晰，语义更明确）
    return `#b#e钓鱼等级#r${fishLevel}级#b（经验：#r${currentExp}/${expPerLevel}#b）\r\n钓鱼成功率加成#r${successRateBonus}%#l#n\r\n\r\n`;
}

function action(mode, type, selection) {
    // 取消/关闭对话处理
    if (mode != 1) {
        cm.dispose();
        return;
    }

    status++;
    // 第一级菜单（选择功能）
    if (status == 0) {
        sel = selection;
        // 进入钓鱼场逻辑
        if (sel == 0) {
            // 任意物品椅子都可用于钓鱼
            if (hasChair()) {
                // 保存当前地图位置，传送至钓鱼场
                cm.getPlayer().saveLocation("MIRROR");
                cm.warp(741000200, 0);
                cm.dispose();
            } else {
                cm.sendNext("你必须拥有一把椅子才能进入钓鱼场！");
                cm.dispose();
            }
        }
        // 购买钓鱼椅逻辑
        else if (sel == 1) {
            // 检查是否已拥有钓鱼椅（每个角色限1个）
            if (cm.haveItem(3011000)) {
                cm.sendNext("你已经有一把钓鱼椅，每个角色只能拥有1个！");
                cm.dispose();
            } else {
                // 检查金币和背包空间
                if (cm.canHold(3011000) && cm.getMeso() >= 5000000) {
                    cm.gainMeso(-5000000); // 扣除500万金币
                    cm.gainItem(3011000, 1); // 发放钓鱼椅
                    cm.sendNext("购买成功！快乐钓鱼~");
                } else {
                    cm.sendOk("请检查是否有500万金币，或背包是否有足够空间！");
                }
                cm.dispose();
            }
        } else if (sel == 2) {
            openNpc("钓鱼/戒指兑换");
        } else if (sel == 3) {
            openNpc("钓鱼/鱼的兑换");
        } else if (sel == 4) {
            openNpc("钓鱼/道具兑换");
        } else if (sel == 5) {
            查看掉落();
        } else if (sel == 999) {
            let text = "\t\t\t\t\t#e#k欢迎来到#r[钓鱼说明]#k系统#n\t\t\t\t\r\n\r\n";
            text += "#r1.在钓鱼区域坐上任意物品椅子，即可进入钓鱼状态\r\n";
            text += `#b2.需要诱饵才能钓鱼，普通鱼饵${Fishing.COMMON_BAIT_BASE_RATE * 100}%成功率，高级鱼饵${Fishing.ADVANCED_BAIT_BASE_RATE * 100}%成功率\r\n`;
            text += "#r3.鱼饵在随身商店中购买\r\n";
            text += `#b4.钓鱼成功后会增加钓鱼等级，每级增加1%的成功率，最高加成${Fishing.MAX_SUCCESS_LEVEL_RATE * 100}%成功率\r\n`;
            text += "5.在自由或者进入钓鱼场都可以钓鱼\r\n";
            text += "6.钓鱼失败也能获取5点卷\r\n";
            cm.sendOk(text);
            cm.dispose();
        }
    }
}

function hasChair() {
    const items = cm.getPlayer().getInventory(InventoryType.SETUP).iterator();
    while (items.hasNext()) {
        if (ItemId.isChair(items.next().getItemId())) {
            return true;
        }
    }
    return false;
}

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}


// 定义掉落类型映射（关联概率+格式化展示）
const dropTypes = [
    {
        type: 1,
        name: "#r普通#k",
        rate: Fishing.ITEM_RATE_COMMON,
        items: Fishing.getInstance().getItemsByType(1, null)
    },
    {
        type: 2,
        name: "#r罕见#k",
        rate: Fishing.ITEM_RATE_UNCOMMON,
        items: Fishing.getInstance().getItemsByType(2, null)
    },
    {type: 3, name: "#r稀有#k", rate: Fishing.ITEM_RATE_RARE, items: Fishing.getInstance().getItemsByType(3, null)},
    {
        type: 4,
        name: "#r超稀有#k",
        rate: Fishing.ITEM_RATE_SUPER_RARE,
        items: Fishing.getInstance().getItemsByType(4, null)
    },
    {
        type: 5,
        name: "#r传奇#k",
        rate: Fishing.ITEM_RATE_LEGENDARY,
        items: Fishing.getInstance().getItemsByType(5, null)
    },
    {
        type: 6,
        name: "#r神话#k",
        rate: Fishing.ITEM_RATE_MYTHIC,
        items: Fishing.getInstance().getItemsByType(6, null)
    }
];

function 查看掉落() {
    // 1. 初始化标题文本
    let text = "\t\t\t\t\t#e#k欢迎来到#r[钓鱼掉落]#k系统#n\t\t\t\t\r\n\r\n";
    // 遍历拼接掉落信息（含概率）
    dropTypes.forEach((dropType) => {
        // 拼接「稀有度 + 概率百分比」
        text += `【${dropType.name}】#b掉落概率：${toPercentage(dropType.rate)}#k\r\n`;

        // 空数据处理
        if (!dropType.items || dropType.items.length === 0) {
            text += "  无掉落物品\r\n\r\n";
            return;
        }

        // 遍历物品
        dropType.items.forEach((itemId) => {
            text += `#v${itemId}##z${itemId}#`;
        });
        text += "\r\n";
    });

    // 发送文本
    cm.sendOk(text);
    cm.dispose();
}

function toPercentage(rate) {
    // 基础转换：小数 → 百分比数值（如0.0001 → 0.01，0.001 → 0.1，0.01 → 1）
    const percent = rate * 100;

    // 1. 万分之级别（< 0.1%）：转中文“万分之X”
    if (percent < 0.1) {
        // 万分比数值 = rate * 10000（如0.0001 → 1，0.0005 → 5，0.00099 → 9.9）
        const perTenThousand = rate * 10000;
        // 优化显示：整数无小数位，非整数保留1位
        const formattedNum = perTenThousand % 1 === 0 ? perTenThousand : perTenThousand.toFixed(1);
        return `万分之${formattedNum}`;
    }
    // 2. 千分之级别（0.1% ≤ 数值 < 1%）：转中文“千分之X”
    else if (percent < 1) {
        // 千分比数值 = rate * 1000（如0.001 → 1，0.0055 → 5.5，0.00999 → 9.99）
        const perThousand = rate * 1000;
        // 优化显示：整数无小数位，非整数保留1位
        const formattedNum = perThousand % 1 === 0 ? perThousand : perThousand.toFixed(1);
        return `千分之${formattedNum}`;
    }
    // 3. 百分级别（≥ 1%）：保持%格式，根据数值适配小数位
    else {
        const perHundred = rate * 100;
        // 优化显示：整数保留0位小数，非整数保留2位（适配88.87%这类场景）
        const formattedNum = perHundred % 1 === 0 ? perHundred : perHundred.toFixed(2);
        return `${formattedNum}%`;
    }
}
