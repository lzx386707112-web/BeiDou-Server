/*
 * 等级阶段性主线任务脚本（优化版）
 * 功能：显示所有主线任务列表, 根据玩家等级判断可接状态, 
 *       已完成任务显示为灰色, 未完成可接任务显示为蓝色
 * 适用：北斗服务器脚本系统
 */

// 配置参数
var 等级 = [10, 30, 50, 70, 90, 120, 140];
var 道具id = [
    [4000019, 4000016, 4000000],   // 10级任务所需道具, 三色蜗牛壳
    [4000012, 4000006, 4000017, 4000330, 4000106],   // 30级任务所需道具 绿蘑菇盖 三眼章鱼触须 猪头 仙人掌的刺 玩具熊的棉花团
    [4000032, 4000024, 4000043, 4000031, 4000060, 4000156],   // 50级任务所需道具 鳄鱼皮 火野猪的尖牙 红螃蟹钳 诅咒娃娃 月光精灵的月块 海象尖牙
    [4000041, 4000014, 4000128, 4000295, 4000027, 4000049, 4000079],   // 70级任务所需道具
    [4000028, 4000053, 4000229, 4000181, 4000267, 4000272, 4000135],   // 90级任务所需道具
    [4000273, 4000407, 4000406, 4000444, 4000445, 4000449, 4000450, 4000454, 4000455],   // 120级任务所需道具
    [2210006, 4000040, 4032474, 4000176, 4000235, 4000243] // 140级任务所需道具
];

var 道具数量 = [
    [200, 200, 200],   // 10级任务所需道具数量
    [200, 200, 10, 200, 200],   // 30级任务所需道具数量
    [200, 200, 200, 200, 200, 200],   // 50级任务所需道具数量
    [200, 200, 200, 200, 200, 200, 200],   // 70级任务所需道具数量
    [30, 30, 100, 200, 200, 100, 100],   // 90级任务所需道具数量
    [500, 100, 100, 100, 100, 100, 100, 100, 100],   // 120级任务所需道具数量
    [10, 10, 10, 10, 10, 10] // 140级任务所需道具数量
];

var 奖励 = [
    [1102039, 4000313, 4001126],   // 10级任务奖励   披风 枫叶5
    [1022048, 4000313, 4001126],   // 30级任务奖励   眼品 枫叶5
    [1032024, 4000313, 4001126],   // 50级任务奖励   耳环 枫叶5
    [1082102, 4000313, 4001126],   // 70级任务奖励   手套 枫叶5
    [1072153, 4000313, 4001126],   // 90级任务奖励   鞋子 枫叶5
    [1002186, 4000313, 4001126],   // 120级任务奖励  帽子 枫叶5
    [1012289, 4000313, 4001126],   // 140级任务奖励  脸饰 枫叶5
];
var 奖励数量 = [
    [1, 10, 5],   // 10级任务奖励   披风 枫叶5
    [1, 10, 5],   // 30级任务奖励   眼品 枫叶5
    [1, 10, 5],   // 50级任务奖励   耳环 枫叶5
    [1, 10, 5],     // 70级任务奖励   手套 枫叶5
    [1, 10, 5],    // 90级任务奖励   鞋子 枫叶5
    [1, 10, 5],   // 120级任务奖励  帽子 枫叶5
    [1, 10, 5],   // 140级任务奖励  脸饰 枫叶5
];

var 奖励金币 = [20, 40, 60, 100, 200, 500, 1000]; // 单位：W
var icon = "#fUI/UIWindow.img/QuestIcon/7/0#";

// 内部变量
var status = -1;
var 玩家等级 = 0;
var 选中任务索引 = -1;
var 基础任务ID = 600001; // 任务ID基础值

function start() {
    玩家等级 = cm.getPlayer().getLevel();
    显示任务列表();
}

function action(mode, type, selection) {
    if (mode === -1) {
        cm.dispose();
        return;
    }

    if (mode === 0) {
        // 玩家取消操作
        if (status === 0) {
            显示任务列表(); // 返回任务列表
        } else {
            cm.dispose();
        }
        return;
    }

    if (status === -1) {
        // 玩家选择了某个任务
        选中任务索引 = selection;
        处理任务选择();
    } else if (status === 1) {
        // 处理任务提交
        完成当前任务();
    }
}

/**
 * 显示所有任务列表, 根据状态设置颜色
 */
function 显示任务列表() {
    var 任务列表文本 = "欢迎来到主线任务中心！以下是所有主线任务列表：\r\n\r\n";
    for (var i = 0; i < 等级.length; i++) {
        var 任务ID = 基础任务ID + i;
        var 任务状态 = "";

        // 判断任务状态并设置颜色
        if (cm.isQuestCompleted(任务ID)) {
            // 已完成任务：灰色
            任务状态 = `#L${i}##r[已完成] Lv.${等级[i]} 主线任务#k#l`;
        } else if (玩家等级 >= 等级[i]) {
            // 可接任务：蓝色
            任务状态 = `#L${i}##b[可接取] Lv.${等级[i]} 主线任务#k#l`;
        } else {
            // 未解锁任务：默认色
            任务状态 = `#L${i}##k[未解锁] Lv.${等级[i]} 主线任务 (需达到${等级[i]}级)#l`;
        }

        任务列表文本 += 任务状态 + "\r\n";
    }

    任务列表文本 += "\r\n请选择你要查看的任务：";
    cm.sendSimple(任务列表文本);
}

/**
 * 处理玩家选择的任务
 */
function 处理任务选择() {
    var 任务ID = 基础任务ID + 选中任务索引;
    var 所需等级 = 等级[选中任务索引];
    var 当前金币奖励 = 奖励金币[选中任务索引] * 10000; // 转换为实际金币数量

    // 已完成任务
    if (cm.isQuestCompleted(任务ID)) {
        cm.sendOk(`#d[已完成] Lv.${所需等级} 主线任务#k\r\n你已经成功完成了这个任务！不能重复完成!`);
        cm.dispose();
        return;
    }

    // 未达到等级
    if (玩家等级 < 所需等级) {
        cm.sendOk(`[未解锁] Lv.${所需等级} 主线任务\r\n该任务需要达到#b${所需等级}级#k才能接取, 请继续提升等级吧！`);
        cm.dispose();
        return;
    }

    // 构建道具需求详情
    var 道具需求文本 = "";
    for (var i = 0; i < 道具id[选中任务索引].length; i++) {
        var 道具ID = 道具id[选中任务索引][i];
        var 所需数量 = 道具数量[选中任务索引][i];
        var 持有数量 = cm.getPlayer().getItemQuantity(道具ID, false);
        道具需求文本 += `#v${道具ID}##t${道具ID}##k: 需要 ${所需数量} 个, 当前持有 ${持有数量} 个\r\n`;
    }
    // 构建奖励详情
    var 奖励文本 = icon + ` × ${奖励金币[选中任务索引]} W \t \r\n`;
    for (var j = 0; j < 奖励[选中任务索引].length; j++) {
        var 奖励ID = 奖励[选中任务索引][j];
        var 奖励个数 = 奖励数量[选中任务索引][j];
        if (j == 0) {
            奖励文本 += `#k#v${奖励ID}##t${奖励ID}##k × ${奖励个数} #b(全属性+5)\r\n`;
        } else {
            奖励文本 += `#k#v${奖励ID}##t${奖励ID}##k × ${奖励个数}\r\n`;
        }
    }

    // 可接取任务：显示详情并询问是否提交
    var 任务详情 = `#b[可接取] Lv.${所需等级} 主线任务#k\r\n\r\n` +
        `任务要求：\r\n\r\n${道具需求文本}\r\n` +
        `完成奖励：\r\n\r\n${奖励文本}\r\n` +
        `是否提交所有任务道具完成任务？`;
    status = 1;
    cm.sendYesNo(任务详情);
}

/**
 * 完成当前选中的任务
 */
function 完成当前任务() {
    var 任务ID = 基础任务ID + 选中任务索引;
    var 任务等级 = 等级[选中任务索引];
    var 道具列表 = 道具id[选中任务索引];
    var 数量列表 = 道具数量[选中任务索引];
    var 奖励列表 = 奖励[选中任务索引];
    var 金币数量 = 奖励金币[选中任务索引] * 10000; // 转换为实际金币数量

    //检查所有道具是否满足数量要求
    for (var i = 0; i < 道具列表.length; i++) {
        var 持有数量 = cm.getPlayer().getItemQuantity(道具列表[i], false);
        if (持有数量 < 数量列表[i]) {
            cm.sendOk(`#v${道具列表[i]}##t${道具列表[i]}##k 数量不足！需要 ${数量列表[i]} 个, 当前只有 ${持有数量} 个`);
            cm.dispose();
            return;
        }
    }
    if (cm.isNotCanHold(1)) {
        return;
    }
    if (cm.isNotCanHold(4)) {
        return;
    }
    // 扣除所有任务道具
    for (var j = 0; j < 道具列表.length; j++) {
        cm.gainItem(道具列表[j], -数量列表[j]);
    }

    // 发放所有奖励道具
    for (var k = 0; k < 奖励列表.length; k++) {
        if (k == 0) {
            //发放攻击时装
            sendEquipment(奖励列表[k]);
        } else {
            cm.gainItem(奖励列表[k], 奖励数量[选中任务索引][k]);
        }
    }
    // 发放金币奖励
    cm.getPlayer().gainMeso(金币数量);
    // 标记任务完成
    cm.completeQuest(任务ID);
    // 构建完成提示文本
    var 完成奖励文本 = 奖励列表.map((id, idx) =>
        `#v${id}##t${id}##k × ${奖励数量[选中任务索引][idx]}`
    ).join("\r\n");
    完成奖励文本 += "\r\n" + icon + ` × ${奖励金币[选中任务索引]} W \t`;
    // 提示完成
    cm.sendOk(`恭喜你完成了 Lv.${任务等级} 主线任务！\r\n获得以下奖励：\r\n${完成奖励文本}`);
    sendSuperMegaphone(cm.getPlayer(), "主线任务", `恭喜玩家${cm.getPlayer().getName()}完成${任务等级}级主线任务!`)
    //蓝色文本
    // cm.getPlayer().dropMessage(6, "完成任务！获得奖励："+完成奖励文本);
    cm.dispose();
}

/**
 * 发装备，除id外都可以传null，传null取装备默认属性
 *
 * @param itemId      装备id
 * @param attStr      力量
 * @param attDex      敏捷
 * @param attInt      智力
 * @param attLuk      运气
 * @param attHp       血量
 * @param attMp       蓝量
 * @param pAtk        物理攻击
 * @param mAtk        魔法攻击
 * @param pDef        物理防御
 * @param mDef        魔法防御
 * @param acc         命中
 * @param avoid       回避
 * @param hands       攻击速度
 * @param speed       移动速度
 * @param jump        跳跃
 * @param upgradeSlot 可升级次数
 * @param expireTime  失效时间，-1为不失效 来自 @leevccc 的建议，传值则为分钟
 */
function sendEquipment(fashionItemId) {
    cm.getPlayer().gainEquip(fashionItemId,
        5,
        5,
        5,
        5,
        100,
        100,
        5,
        5,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        -1
    );
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
