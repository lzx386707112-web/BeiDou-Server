/**北斗脚本
 签到脚本
 ---By hanmburger (优化版)*/
var status = -1;
var DAILY_CHECK_IN = "是否每日已签到"
var DAILY_CHECK_IN_TOTAL = "累计签到次数"
var DAILY_CHECK_IN_TOTAL_CLAIM = "是否已领取累计签到奖励"
var column = ["3", "5", "7", "15", "30", "60", "90", "120", "180", "240", "360"];
var itemId = 2430033;

// 定义每日签到奖励物品信息
var dailyRewards = [
    {id: itemId, qty: 5},
    {id: 2029004, qty: 1},//双倍经验
    {id: 2029002, qty: 1}//双倍爆率
];

// 定义累计签到奖励物品信息（每个奖励都增加了2029004 x1）
var accumulateRewards = {
    "3": [
        {id: itemId, qty: 10},
        {id: 2029004, qty: 2},
        {id: 2029005, qty: 2},
        {id: 4310000, qty: 1},
    ],
    "5": [
        {id: itemId, qty: 10},
        {id: 2029004, qty: 3},
        {id: 2029005, qty: 3},
        {id: 4310000, qty: 1},
        {id: 4000325, qty: 1},//胡罗卜
    ],
    "7": [
        {id: itemId, qty: 10},
        {id: 2029004, qty: 3},
        {id: 2029005, qty: 3},
        {id: 2340000, qty: 5},	//祝福
        {id: 2049100, qty: 5},	//混沌
        {id: 4032133, qty: 2},	//红色钻石
    ],
    "15": [
        {id: itemId, qty: 10},
        {id: 2029004, qty: 5},
        {id: 2029005, qty: 5},
        {id: 2340000, qty: 5},	//祝福
        {id: 2049100, qty: 5},	//混沌
        {id: 4032133, qty: 2},	//红色钻石
    ],
    "30": [
        {id: itemId, qty: 20},
        {id: 2029004, qty: 6},
        {id: 2029005, qty: 6},
        {id: 2340000, qty: 10},	//祝福
        {id: 2049100, qty: 10},	//混沌
        {id: 4032133, qty: 5},	//红色钻石
        {id: 4000325, qty: 1},//胡罗卜
    ],
    "60": [
        {id: itemId, qty: 20},
        {id: 2029004, qty: 10},
        {id: 2029005, qty: 10},
        {id: 2340000, qty: 20},	//祝福
        {id: 2049100, qty: 20},	//混沌
        {id: 4032133, qty: 10},	//红色钻石
        {id: 4000325, qty: 1},//胡罗卜
    ],
    "90": [
        {id: itemId, qty: 30},
        {id: 2029004, qty: 10},
        {id: 2029005, qty: 10},
        {id: 2340000, qty: 30},	//祝福
        {id: 2049100, qty: 30},	//混沌
        {id: 4032133, qty: 20},	//红色钻石
        {id: 4000325, qty: 1},//胡罗卜
    ],
    "120": [
        {id: itemId, qty: 40},
        {id: 2029004, qty: 20},
        {id: 2029005, qty: 20},
        {id: 2340000, qty: 100},//祝福
        {id: 2049100, qty: 100},//混沌
        {id: 4032133, qty: 100},//红色钻石
        {id: 4000325, qty: 1},//胡罗卜
    ],
    "180": [
        {id: itemId, qty: 40},
        {id: 2029004, qty: 20},
        {id: 2029005, qty: 20},
        {id: 2340000, qty: 100},//祝福
        {id: 2049100, qty: 120},//混沌
        {id: 4032133, qty: 120},//红色钻石
        {id: 4000325, qty: 10},//胡罗卜
    ],
    "240": [
        {id: itemId, qty: 40},
        {id: 2029004, qty: 20},
        {id: 2029005, qty: 20},
        {id: 2340000, qty: 100},//祝福
        {id: 2049100, qty: 150},//混沌
        {id: 4032133, qty: 150},//红色钻石
        {id: 4000325, qty: 10},//胡罗卜
    ],
    "360": [
        {id: itemId, qty: 40},
        {id: 2029004, qty: 20},
        {id: 2029005, qty: 20},
        {id: 2340000, qty: 100},//祝福
        {id: 2049100, qty: 250},//混沌
        {id: 4032133, qty: 200},//红色钻石
        {id: 4000325, qty: 10},//胡罗卜
    ],
};

function start() {
    status = -1;
    levelStart();
}


function levelStart() {
    let text = "#d您已累计签到 #r" + getCurCheckInCount() + " #d天\r\n\r\n";
    text += "#L0##b每日签到  " + getCheckInState() + "#l\r\n\r\n";
    // text+="\t#n#d(奖励:";
    // dailyRewards.forEach(reward => {
    //     text += `#t${reward.id}# x ${reward.qty}`;
    // });
    // text+=")\r\n#b#n";
    text += "\r\n";
    text += "#L1##b领取累计签到奖励#l\n";
    cm.sendSelectLevel(text);
}

//每日签到
function level0() {
    text = cm.getAccountExtendValue(DAILY_CHECK_IN, true);
    if (text === "1") {
        cm.sendOk("您已经签到过了，请明天再来");
        cm.dispose();
    } else {
        if (canHold(dailyRewards)) { // 检查足够的背包空间
            saveCheckInCount();
            cm.saveOrUpdateAccountExtendValue(DAILY_CHECK_IN, "1", true);
            // 构建每日奖励提示
            let rewardText = "签到成功！获得以下奖励：\r\n\r\n";
            dailyRewards.forEach(reward => {
                rewardText += `#v${reward.id}##t${reward.id}# x ${reward.qty}\r\n`;
            });
            cm.sendOk(rewardText);
            // 发放每日奖励
            dailyRewards.forEach(reward => {
                cm.gainItem(reward.id, reward.qty);
            });
            sendSuperMegaphone(cm.getPlayer(), "每日签到", `恭喜玩家${cm.getPlayer().getName()}签到成功!`);
            cm.dispose();
        }
    }
}

function canHold(list) {
    for (const {id, qty} of list) {
        if (!cm.canHold(id, qty)) {
            cm.sendOk("背包空间不足");
            cm.dispose();
            return false;
        }
    }
    return true;
}

function getCheckInState() {
    text = cm.getAccountExtendValue(DAILY_CHECK_IN, true);
    return text === "1" ? " #r(已签到)" : "(未签到)";
}

function getAccumulateCheckInState(type) {
    text = cm.getAccountExtendValue(type);
    return text === "1" ? " #r(已领取)" : "(未领取)";
}

//领取累计奖励列表展示
function level1() {
    let text = "#e请确保您的背包空间足够，再领取奖励#n\r\n\r\n";
    for (let i = 1; i <= column.length; i++) {
        let index = column[i - 1];
        // 预览累计奖励内容
        text += `#L${i}##b${index}天奖励${getAccumulateCheckInState(DAILY_CHECK_IN_TOTAL_CLAIM + index)}#l\r\n\r\n`;
    }
    cm.sendNextSelectLevel("ChooseInventory", text);
}

// 发放累计奖励
function levelChooseInventory(choose) {
    let index = column[choose - 1];
    let curCheckInCount = getCurCheckInCount();
    let tag = DAILY_CHECK_IN_TOTAL_CLAIM + index;
    let isClaim = cm.getAccountExtendValue(tag);
    let rewards = accumulateRewards[index];
    if (curCheckInCount < Number(index) || isClaim === "1") {
        if (curCheckInCount < Number(index)) {
            // 未达到天数时显示完整奖励列表
            let tip = `#r未达到领取天数（当前${curCheckInCount}天，需${index}天）\r\n\r\n奖励内容：\r\n`;
            rewards.forEach(reward => {
                tip += `#v${reward.id}##t${reward.id}# x ${reward.qty}\r\n`;
            });
            cm.sendOk(tip);
        } else {
            cm.sendOk("#r您已领取过该累计签到奖励");
        }
        cm.dispose();
    } else {
        if (!cm.isNotCanHold(2, rewards.length)) { // 检查背包空间是否足够
            // 领取成功提示
            let tip = "#b恭喜您，领取成功！获得以下奖励：\r\n\r\n";
            rewards.forEach(reward => {
                tip += `#v${reward.id}##t${reward.id}# x ${reward.qty}\r\n`;
            });
            cm.sendOk(tip);
            // 发放所有累计奖励
            rewards.forEach(reward => {
                cm.gainItem(reward.id, reward.qty);
            });
            cm.saveOrUpdateAccountExtendValue(tag, "1");
            sendSuperMegaphone(cm.getPlayer(), "累计签到", `恭喜玩家${cm.getPlayer().getName()}领取${index}天累计签到奖励!`);
            cm.dispose();
        }
    }
}


//当前签到次数
function getCurCheckInCount() {
    let dayCount = cm.getAccountExtendValue(DAILY_CHECK_IN_TOTAL);
    return Number(dayCount) || 0; // 处理未签到过的情况
}

//当前签到次数+1并保存
function saveCheckInCount() {
    cm.saveOrUpdateAccountExtendValue(DAILY_CHECK_IN_TOTAL, String(getCurCheckInCount() + 1));
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
