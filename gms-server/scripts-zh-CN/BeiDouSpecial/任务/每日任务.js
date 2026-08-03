/**
 * 每日任务脚本
 * 功能：每日10轮任务，按等级匹配道具要求，支持提交/跳过，依赖AccountExtendValue的24小时自动清除机制重置
 */

var status = -1;
var currentRound = 1; // 当前轮次
const maxRounds = 10; // 最大轮次
const CashPoint1Num = 1000; // 点券奖励
const MesoNum = 20; // 金币奖励,单位W
var selectedItemId = 0; // 当前任务道具ID
var requiredItemCount = 0; // 当前任务所需道具数量
var 额外奖励次数 = 8;
var 声望 = 6000;
// 定义每日签到奖励物品信息
var 奖励道具集合 = [
    {id: 2029004, qty: 1},//三倍经验
    {id: 2029002, qty: 1}//双倍经验
];

// 存储键名定义
const ROUND_KEY = "每日任务当前第几轮";
const TOTAL_COMPLETE_KEY = "每日任务总完成轮数";
const ITEM_ID_KEY = "每日任务当前道具ID";
const ITEM_COUNT_KEY = "每日任务当前道具数量";

// 任务道具配置（按等级段划分）
var itemPools = [
    [[4000019, 10], [4000012, 10], [4000002, 15], [4000215, 10], [4000034, 10], [4000331, 10]],    //20 绿色蜗牛壳, 绿蘑菇盖, 蝴蝶结, 斧头,蛇皮,仙人掌的花
    [[4000007, 10], [4000020, 15], [4000196, 10], [4000106, 10]],   // 20级 火独眼兽之尾, 野猪尖牙, 木板, 玩具熊猫的棉花团
    [[4000032, 10], [4000073, 10], [4000108, 10], [4000096, 10], [4000110, 10], [4000031, 10]],   // 40级 鳄鱼皮, 独角狮硬角,熊猫娃娃, 硬胡桃,木马骑兵的剑,诅咒娃娃
    [[4000014, 10], [4000023, 10], [4000178, 10], [4000060, 10], [4000205, 10]],   // 30级 龙的头骨, 冰独眼兽之尾, 钢甲猪盔甲,月光精灵的月块,绷带
    [[4000069, 10], [4000022, 10], [4000051, 10], [4000440, 10]],   // 60级 僵尸丢失的臼齿, 石块, 野狼之尾, 粗糙的皮革
    [[4000074, 10], [4000295, 10], [4000289, 10], [4000027, 10]],   // 70级 黑色飞狮尾, 鳄鳄的皮, 猫咪娃娃、怪猫的眼
    [[4000226, 10], [4000028, 5], [4000232, 10], [4000242, 10]],   // 80级 莱西毛球、月牙牛魔王的角、半人马的火花、恶魔绵羊尾巴
    [[4000262, 10], [4000477, 10], [4000430, 10]],   // 90级 有裂痕的背壳 海盗头盔 怪虫迪波之角
    [[4000184, 10], [4000135, 10], [4000268, 10], [4000269, 10], [4000270, 10]],   // 100级 奶油烤章鱼 大海贼王的帽子 飞龙的翅膀 飞龙的腮 飞龙的指甲 大海贼王的帽子
    [[4000274, 15], [4000434, 15]]   // 110级 断裂的角 大花草
];


function start() {
    // 加载存储的任务数据
    loadTaskData();
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === -1) {
        // 关闭对话框时保存当前进度
        saveTaskProgress();
        cm.dispose();
        return;
    }

    // 处理状态流转
    if (mode === 1) {
        status++;
    } else {
        status--;
    }
    // 主界面逻辑
    if (status === 0) {
        if (currentRound > maxRounds) {
            cm.sendOk("今日10轮任务已全部完成，明天再来挑战吧！\r\n\r\n");
            cm.dispose();
            return;
        }
        // 显示当前轮次任务信息和操作选项
        let text = `#k每日任务 第 #r${currentRound}/${maxRounds} #k轮\r\n\r\n` +
            `#b每轮奖励：#k\r\n` +
            `- ${CashPoint1Num} 点券\r\n` +
            `- ${MesoNum} w金币\r\n\r\n` +
            获取奖励文本() +
            `#b当前任务要求：\r\n` +
            `#b#i${selectedItemId}# #t${selectedItemId}# × ${requiredItemCount}\r\n\r\n` +
            `#k请选择操作：\r\n` +
            `#r#L0#提交任务#l\r\n` +  // 使用换行符分隔选项，避免索引识别错误
            `#k#L1#跳过本轮(不获取奖励)#l`;
        cm.sendSimple(text);
    } else if (status === 1) {
        if (selection === 0) {//点击提交
            completeTask();
        } else if (selection === 1) {//点击跳过
            // 显示跳过确认提示
            cm.sendYesNo(`确定要跳过第 ${currentRound} 轮任务吗？\r\n跳过本轮将不会获得任何奖励，直接进入下一轮。`);
        }
    } else if (status === 2) {//确认跳过
        // 确认跳过（mode=1），取消跳过（mode=0）
        if (mode === 1) {
            skipTask();
        }
    }
}

function 获取奖励文本() {
    let text = "#b第10轮，并且当天总完成次数大于8轮：#k\r\n";
    奖励道具集合.forEach(reward => {
        text += `- #v${reward.id}##t${reward.id}# x ${reward.qty}\r\n`;
    });
    text += `- 学院声望 x #r${声望}\r\n`;
    text += "\r\n";
    return text;
}

/**
 * 加载存储的任务数据
 */
function loadTaskData() {
    const savedRound = cm.getAccountExtendValue(ROUND_KEY, true);
    currentRound = savedRound ? parseInt(savedRound) : 1;
    currentRound = savedRound <= 0 ? 1 : parseInt(savedRound);

    const savedTotalComplete = cm.getAccountExtendValue(TOTAL_COMPLETE_KEY, true);
    // 初始化总完成次数（默认0）
    totalCompleteCount = savedTotalComplete ? parseInt(savedTotalComplete) : 0;

    const savedItemId = cm.getAccountExtendValue(ITEM_ID_KEY, true);
    selectedItemId = savedItemId ? parseInt(savedItemId) : 0;
    const savedItemCount = cm.getAccountExtendValue(ITEM_COUNT_KEY, true);
    requiredItemCount = savedItemCount ? parseInt(savedItemCount) : 0;

    if (selectedItemId === 0 || requiredItemCount === 0) {
        generateTask();
        saveTaskProgress();
    }
}

/**
 * 重置每日任务状态
 */
function resetDailyTask() {
    currentRound = 1;
    totalCompleteCount = 0; // 重置总完成次数
    selectedItemId = 0;
    requiredItemCount = 0;
}

/**
 * 保存当前任务进度
 */
function saveTaskProgress() {
    cm.saveOrUpdateAccountExtendValue(ROUND_KEY, currentRound.toString(), true);
    cm.saveOrUpdateAccountExtendValue(TOTAL_COMPLETE_KEY, totalCompleteCount.toString(), true); // 保存总完成次数
    cm.saveOrUpdateAccountExtendValue(ITEM_ID_KEY, selectedItemId.toString(), true);
    cm.saveOrUpdateAccountExtendValue(ITEM_COUNT_KEY, requiredItemCount.toString(), true);
}

/**
 * 根据玩家等级生成对应任务道具
 */
function generateTask() {
    const playerLevel = cm.getPlayer().getLevel();
    let availableItems = [];

    // 按等级筛选可用道具池
    if (playerLevel < 20) {
        availableItems = [...itemPools[0]];
    } else if (playerLevel < 30) {
        availableItems = [...itemPools[0], ...itemPools[1]];
    } else if (playerLevel < 40) {
        availableItems = [...itemPools[0], ...itemPools[1], ...itemPools[2]];
    } else if (playerLevel < 50) {
        availableItems = [...itemPools[1], ...itemPools[2], ...itemPools[3]];
    } else if (playerLevel < 60) {
        availableItems = [...itemPools[2], ...itemPools[3], ...itemPools[4]];
    } else if (playerLevel < 70) {
        availableItems = [ ...itemPools[3], ...itemPools[4], ...itemPools[5]];
    } else if (playerLevel < 80) {
        availableItems = [...itemPools[4], ...itemPools[5], ...itemPools[6]];
    } else if (playerLevel < 90) {
        availableItems = [...itemPools[5], ...itemPools[6], ...itemPools[7]];
    } else if (playerLevel < 100) {
        availableItems = [...itemPools[6], ...itemPools[7], ...itemPools[8]];
    } else {
        availableItems = [...itemPools[7], ...itemPools[8], ...itemPools[9]];
    }

    // 随机选择一个道具
    const randomIndex = Math.floor(Math.random() * availableItems.length);
    selectedItemId = availableItems[randomIndex][0];
    requiredItemCount = availableItems[randomIndex][1];
}

/**
 * 处理任务完成逻辑
 */
function completeTask() {
    if (cm.haveItem(selectedItemId, requiredItemCount)) {
        // 检查背包空间
        if (cm.isNotCanHold(2)) {
            return;
        }
        // 1. 总完成次数+1并保存
        totalCompleteCount++;

        // 2. 进入下一轮
        const completedRound = currentRound; // 记录当前完成的轮次
        currentRound++;

        // 3. 扣除道具
        cm.gainItem(selectedItemId, -requiredItemCount);
        // 4. 发放基础奖励
        cm.gainMeso(MesoNum * 10000);
        cm.getPlayer().getCashShop().gainCash(1, CashPoint1Num);

        // 5. 第10轮任务完成时，判断是否发放额外道具（总完成次数>8）
        let extraRewardText = "";
        if (completedRound === maxRounds) {
            // 总完成次数>8时发放额外道具
            if (totalCompleteCount >= 额外奖励次数) {
                发放道具();
                //发放6000声望
                // cm.getPlayer().getFamilyEntry().gainReputation(声望, true);
                extraRewardText = `- 额外奖励：\r\n`;
                奖励道具集合.forEach(item => {
                    extraRewardText += `  #v${item.id}##t${item.id}# x ${item.qty}\r\n`;
                });
                extraRewardText += `  学院声望 x #r${声望}\r\n`;
                sendRandomSceneMegaphone(cm.getPlayer(), "每日任务", `恭喜玩家${cm.getPlayer().getName()}完成每日任务10次!`)
            } else {
                extraRewardText = `- 今日总完成次数不足${额外奖励次数}次，未获得额外道具奖励\r\n`;
            }
        }

        // 6. 生成下一轮任务（如果未完成全部轮次）
        if (currentRound <= maxRounds) {
            generateTask();
        }

        // 7. 保存进度并提示
        saveTaskProgress();
        status = -1;
        let text = `#b恭喜完成第 #r${completedRound}/${maxRounds} #b轮任务（成功完成${totalCompleteCount}轮任务）！\r\n\r\n` +
            `获得奖励：\r\n` +
            `- #r${CashPoint1Num} #b点券\r\n` +
            `- #r${MesoNum} #bW金币\r\n`;
        if (completedRound === maxRounds) {
            text += extraRewardText;
        }
        cm.sendNext(text);
    } else {
        // 道具不足时返回主界面
        cm.sendOk(
            `你的 #t${selectedItemId}# #r数量不足\r\n` +
            `#b需要：#r${requiredItemCount} #b个  当前持有：#r${cm.getItemQuantity(selectedItemId) || 0} #b个\r\n\r\n`
        );
        cm.dispose();
    }
}

/**
 * 发放额外道具奖励
 */
function 发放道具() {
    奖励道具集合.forEach(item => {
        cm.gainItem(item.id, item.qty);
    });
}

/**
 * 跳过当前任务（带确认流程）
 */
function skipTask() {
    // 进入下一轮并生成新任务（跳过不增加总完成次数）
    currentRound++;
    if (currentRound <= maxRounds) {
        generateTask();
    }
    saveTaskProgress();
    // 显示跳过成功提示后返回主界面
    status = -1;
    action(1, 0, 0);
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
