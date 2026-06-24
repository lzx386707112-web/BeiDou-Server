/**
 * @description 拍卖行中心脚本
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[其他功能]#k系统#n\t\t\t\t\r\n";
var status = -1;
// 存储键：用于标记是否已领取公测礼包（避免重复领取）
const TEST_PACKAGE_KEY = "公测测试礼包领取状态";

function start() {
    action(1, 0, 0)
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else if (mode === -1) {
        cm.dispose();
        return;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        let text = OldTitle;
        text += " \r\n";
        text += `#r#L0#【${节日str}】节日礼物#l\r\n\r\n`;
        text += "#b#L2#常用指令查询#l\r\n\r\n";
        text += "#b#L4#灵魂戒指领取#l\r\n\r\n";
        // text += "#b#L1#领取公测测试礼包（正式开服无该礼包）#l\t\r\n\r\n";
        // text += "#b#L3#测试期间道具领取#l\t\r\n\r\n";
        cm.sendSimple(text);
    } else if (status === 1) {
        doSelect(selection);
    } else {
        cm.dispose();
    }
}

function doSelect(selection) {
    switch (selection) {
        case 0:
            try {
                发放奖励();
            } catch (e) {
                cm.dispose();
                // 打印错误日志便于调试
                console.error("主菜单脚本错误===》:", e);
            }
            break;
        case 2:
            openNpc("常用指令");
            break;
        case 3:
            cm.gainItem(4032133, 500);
            cm.gainItem(2049100, 500);
            cm.gainItem(2029005, 200);
            break;
        case 4:
            openNpc("灵魂戒指");
            break;
        default:
            cm.sendOk("该功能暂不支持，敬请期待！");
            cm.dispose();
    }
}


var 枫叶奖励 = 4032133;
var 枫叶数量 = 5;
var 奖励_KEY = "补偿奖励_v8"
var meso_id = 9999999;
var cash_id = 9999998;
let 节日str = "儿童节";

var rewards = [
    {id: cash_id, qty: 80000},//点卷
    {id: meso_id, qty: 5000},
    {id: 4032133, qty: 40},//红色钻石
    {id: 4260010, qty: 50},//低级强化宝石
    {id: 4260009, qty: 20},//中级强化宝石
    {id: 4039020, qty: 50},//金蛋
    {id: 2029005, qty: 10},//三倍经验
    {id: 2029002, qty: 15},//双倍爆率
    {id: 2049116, qty: 20},//正向
    {id: 2340001, qty: 50},//祝福
];
// const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
// const ItemConstants = Java.type('org.gms.constants.inventory.ItemConstants');
// const KarmaManipulator = Java.type('org.gms.client.inventory.manipulator.KarmaManipulator');

function 发放奖励() {
    // 检查是否已领取过礼包
    if (cm.getAccountExtendValue(奖励_KEY) === "1") {
        cm.sendOk("你已经领取过节日奖励啦！");
        cm.dispose();
        return;
    }
    if (cm.isNotCanHold(1)) {
        return;
    }
    if (!canHold()) {
        return;
    }
    var player = cm.getPlayer();
    rewards.forEach(reward => {
        if (reward.id === meso_id) {
            cm.gainMeso(reward.qty * 10000);
        } else if (reward.id === cash_id) {
            cm.getPlayer().getCashShop().gainCash(1, reward.qty);//点券
        } else {
            let qty = reward.qty;
            // 生成 -1 ~ +2 的随机偏移量（关键）
            const randomOffset = Math.floor(Math.random() * 4) - 1; // 0~3 随机数 -1 → -1/0/1/2
            qty += randomOffset;
            qty = Math.max(qty, 1);
            cm.gainItem(reward.id, qty);
        }
    });
    // sendEquipment(1702920, -1);
    cm.saveOrUpdateAccountExtendValue(奖励_KEY, "1");
    cm.sendOk("恭喜你领取成功");
    cm.getPlayer().sendAllWordNoticeNew(3, "节日礼物", `恭喜玩家【${cm.getPlayer().getName()}】领取【${节日str}】礼物! 祝大家节日快来，玩的开心~~`);
    全服通告();
    cm.dispose();
}

function canHold() {
    for (const {id, qty} of rewards) {
        if (id == 9999999 || id == 9999998) {
            continue;
        }
        if (!cm.canHold(id, qty)) {
            cm.sendOk("背包空间不足！");
            cm.dispose();
            return false;
        }
    }
    return true;
}

function 全服通告() {
    let tip = `恭喜玩家【${cm.getPlayer().getName()}】领取【${节日str}】礼物! 祝大家节日快来，玩的开心~~`;
    cm.getPlayer().sendFullServerBroadcast(tip);
}

function openNpc(scriptName) {
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}

function sendEquipment(fashionItemId, time) {
    cm.getPlayer().gainEquip(fashionItemId,
        30,
        30,
        80,
        30,
        200,
        200,
        30,
        80,
        0,
        0,
        0,
        0,
        0,
        20,
        0,
        0,
        time
    );
}