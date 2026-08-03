/*
 * 世界任务
 */
const ExpTable = Java.type('org.gms.constants.game.ExpTable');
// 配置参数
var 任务需要的道具 = [
    [[4000227, 888], [4000136, 111]],    //1 树果实  椰子果
    [[4000058, 888], [4000062, 888]],    //2 食人花的种子，黑食人花的种子
    [[4000232, 888], [4000233, 888], [4000234, 888]],    //3 半人马的火花，半人马的净水，半人马的骨头
    [[4000238, 888], [4000239, 888], [4000240, 188]],    //4 哈维羽毛 血腥哈维的王冠，小火花羽毛
    [[4000189, 888], [4000194, 888]],    //5 羊毛 黑羊毛
    [[4000076, 888], [4000042, 888]],    //6  独眼蝙蝠之翼 蝙蝠翅膀
    [[4000244, 222], [4000245, 222]],    //7 蓝色双角龙的灵魂 蓝色双角龙的鳞片
    [[4000084, 666], [4000085, 666]],    //8 冰石球的石片 火石球的石片
    [[4000028, 111], [4000046, 111]],    //9 月牙牛魔王的角 长枪牛魔王之角
    [[4000054, 222], [4005004, 10], [4000024, 888]],    //10 白狼人脚趾 黑水晶 火野猪尖牙
    [[4000017, 66], [4000039, 888]],    //11 猪头 钢铁猪蹄
    [[4000011, 666], [4000398, 666]],    //12 蘑菇芽孢 木鱼妖怪
    [[4000124, 33], [4000164, 666]],    //13 战甲鱼吹泡泡的内存卡 蓝泡泡翻车鱼之心
    [[4000397, 666], [4000396, 666]],    //14 飞贼腿带 飞贼护手
    [[4000056, 666], [4000049, 666]],    //15 黑雪人的角 白雪人的角
    [[4000082, 88], [4000406, 88]],    //16  僵尸丢失的金齿 金人心
    [[4000068, 188], [4000431, 666]],    //17 蝴蝶精的触角 蚯蚓之尾
    [[4000170, 888], [4000171, 888]],    //18 老虎脚印 虎皮
    [[4000168, 888], [4000095, 888], [4000109, 888]],    //19 向日葵子 老鼠陷阱  玩具小鸭
    [[4000030, 888], [2012000, 118]],    //20 龙皮 龙血
    [[2012002, 118], [4003002, 66]],    //21 古木树液 冰块
    [[4000186, 888], [4000175, 12]],    //22 黑龙之角 屁亚奴斯模型
    [[2210006, 33], [4000040, 33], [4000176, 33]],    //23 彩虹色蜗牛壳 蘑菇王芽孢 毒菇
    [[4000235, 33], [4000243, 33]],    //24 喷火龙的尾巴 格瑞芬多角
    [[4000460, 33], [4000461, 33], [4000462, 33]]     //25 古代头盔 骑士面具 守护兽之角
];

var startItemId = 2430681;
var itemId
var 奖励 = [
    [4032170, 10],  // 奖励道具1及数量
    [4032171, 10],    // 奖励道具2及数量
    [2029004, 2],    //
    [2029002, 1],    //
    [4032133, 2],    //
];
var 首次完成金币 = 1000;  // 1000W金币
var 重复完成金币 = 100;   // 200W金币
var 基础任务ID = 200001;  // 任务ID基础值，用于标记完成状态
var 当前任务 = -1;  // 当前任务编号（1-25）
var 任务索引 = 当前任务 - 1;  // 转换为数组索引（0-24）
var 经验奖励 = 50000000;  // 千W经验

// 内部变量
var status = -1;
var icon = "#fUI/UIWindow.img/QuestIcon/7/0#";
var icon_exp = "#fUI/UIWindow.img/QuestIcon/8/0#";

function start() {
    获取奖励经验();
    显示当前任务详情();
}

function action(mode, type, selection) {
    获取奖励经验();
    if (mode === -1) {
        im.dispose();
        return;
    }

    if (mode === 0) {
        // 玩家取消操作
        im.dispose();
        return;
    }

    if (status === 0) {
        // 处理任务提交
        处理任务提交();
    }
}

/**
 * 显示当前任务的详情信息
 */
function 显示当前任务详情() {
    //获取当前点击的任务品id
    itemId = im.getItemId();
    任务索引 = itemId - startItemId
    当前任务 = 任务索引 + 1;
    if (任务索引 < 0 || 当前任务 <= 0 || 当前任务 > 25) {
        im.sendOk(`未知错误，请联系管理员=` + 任务索引 + " $ " + 当前任务);
        im.dispose();
    }

    var 任务ID = 基础任务ID + 任务索引;
    var isCompleted = im.isQuestCompleted(任务ID);
    // var isCompleted =true;
    var 任务状态 = isCompleted ? "[已完成，重复完成奖励降低]#k" : "[未完成]#k";

    // 构建道具需求文本
    var 道具需求文本 = "";
    for (var i = 0; i < 任务需要的道具[任务索引].length; i++) {
        var 道具ID = 任务需要的道具[任务索引][i][0];
        var 所需数量 = 任务需要的道具[任务索引][i][1];
        var 持有数量 = im.getPlayer().getItemQuantity(道具ID, false);
        道具需求文本 += `#v${道具ID}##t${道具ID}##k: 需要 ${所需数量} 个, 当前持有 ${持有数量} 个\r\n`;
    }

    // 构建奖励文本
    var 奖励文本 = icon + ` × ${isCompleted ? 重复完成金币 : 首次完成金币} W \r\n`;
    if (!isCompleted) {
        奖励文本 += icon_exp + ` × ${经验奖励}\r\n#b(等级越高获取的经验越多,最高5000W经验)#k\r\n`;
        for (var j = 0; j < 奖励.length; j++) {
            var 奖励ID = 奖励[j][0];
            var 奖励个数 = 奖励[j][1];
            奖励文本 += `#v${奖励ID}##t${奖励ID}##k × ${奖励个数}\r\n`;
        }
    }
    // 构建任务详情
    var 任务详情 = `#r#e【世界任务${当前任务}】   #n#b${任务状态} \r\n\r\n` +
        `任务要求：\r\n\r\n${道具需求文本}\r\n` +
        `完成奖励：\r\n\r\n${奖励文本}\r\n` +
        (isCompleted ? "该任务已完成，再次提交可获得部分金币奖励" : "是否提交所有任务道具完成任务？");

    status = 0;
    im.sendYesNo(任务详情);
}

/**
 * 处理任务提交逻辑
 */
function 处理任务提交() {
    var 任务ID = 基础任务ID + 任务索引;
    var 道具列表 = 任务需要的道具[任务索引];

    // 检查所有道具是否满足数量要求
    for (var i = 0; i < 道具列表.length; i++) {
        var 道具ID = 道具列表[i][0];
        var 所需数量 = 道具列表[i][1];
        var 持有数量 = im.getPlayer().getItemQuantity(道具ID, false);

        if (持有数量 < 所需数量) {
            im.sendOk(`#v${道具ID}##t${道具ID}##k 数量不足！需要 ${所需数量} 个, 当前只有 ${持有数量} 个`);
            im.dispose();
            return;
        }
    }

    // 检查背包空间
    if (im.isNotCanHold(4)) {  // 检查其他类型背包
        return;
    }

    // 扣除任务道具
    for (var j = 0; j < 道具列表.length; j++) {
        im.gainItem(道具列表[j][0], -道具列表[j][1]);
    }
    im.gainItem(itemId, -1);
    // 判断是否首次完成
    var 首次完成 = !im.isQuestCompleted(任务ID);
    var 金币奖励 = 首次完成 ? 首次完成金币 : 重复完成金币;

    // 发放奖励
    if (首次完成) {
        // 首次完成发放道具奖励
        for (var k = 0; k < 奖励.length; k++) {
            im.gainItem(奖励[k][0], 奖励[k][1]);
        }
        //发放经验奖励
        im.gainExp(经验奖励);
        // 标记任务完成
        im.completeQuest(任务ID);
    }
    // 发放金币奖励
    im.getPlayer().gainMeso(金币奖励 * 10000);
    // 构建完成提示
    var 完成提示 = `恭喜你完成#r#e【世界任务${当前任务}】#n#k！\r\n获得奖励：\r\n\r\n`;
    完成提示 += icon + ` × ${金币奖励} W\r\n`;
    if (首次完成) {
        完成提示 += icon_exp + ` × ${经验奖励}\r\n`;
        for (var m = 0; m < 奖励.length; m++) {
            完成提示 += `#v${奖励[m][0]}##t${奖励[m][0]}##k × ${奖励[m][1]}\r\n`;
        }
    }
    im.sendOk(完成提示);
    sendRandomSceneMegaphone(im.getPlayer(), 3, "世界任务", `恭喜肝帝${im.getPlayer().getName()}完成世界任务${当前任务}!`)
    im.dispose();
}



function 获取奖励经验() {
    let levelExp = getNeedExp();
    if (levelExp < 经验奖励) {
        经验奖励 = levelExp;
    }
}

function getNeedExp() {
    return ExpTable.getExpNeededForLevel(im.getPlayer().getLevel());
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
