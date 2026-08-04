/**
 * 每日装备强化
 * @type {string}
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[装备强化]#k系统#n\t\t\t\t\r\n";
var status = -1;
var 强化目标项链Id = 1122017; // 目标装备ID
var KERNING_COMPLETION_COUNT = "废弃副本完成次数"; // 记录废弃副本完成次数的键
var 精灵项链强化key = "精灵项链强化已强化"; // 记录今日是否已强化的键
var 已强化值 = "1";
var need_kerning_completion_count = 1; // 需要完成的废弃副本次数

function start() {
    status = -1;
    try {
        action(1, 0, 0);
    } catch (e) {
        cm.dispose();
        // 打印错误日志便于调试
        console.error("主菜单脚本错误===》:", e);
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
            do强化(); // 执行强化操作
        } else {
            cm.dispose(); // 无效选择直接关闭
        }
    } else {
        cm.dispose();
    }
}

/**
 * 主界面：展示强化信息和条件
 */
function main() {
    let text = OldTitle;
    text += " \r\n";
    text += `#b这里每天可以帮你强化#v${强化目标项链Id}##z${强化目标项链Id}#道具1次#k\r\n`;
    text += "强化条件:\r\n";
    text += "1. 完成废弃副本至少1次\r\n";
    text += `2. 请将#v${强化目标项链Id}##t${强化目标项链Id}# 放在装备栏第一格\r\n`;
    text += "3. 强化后魔攻、智力、血蓝+2，其余全属性+1\r\n";
    text += "4. 一个账号每日只能强化1次\r\n\r\n";

    // 检查今日是否已强化（带日期后缀，支持每日重置）
    if (是否已强化过()) {
        text += "\r\n#r你今天已经强化过了，请明天再来！#k";
        cm.sendOk(text);
        cm.dispose();
        return;
    }
    var kerningCompletionCount = 获取废弃副本完成次数();
    let 废弃副本是否满足条件 = kerningCompletionCount >= need_kerning_completion_count;
    var str = 废弃副本是否满足条件 ? "#b满足条件#k" : "#r不满足条件#k";
    text += `#b您已完成废弃副本${kerningCompletionCount}次, ${str}\r\n`;
    if (废弃副本是否满足条件) {
        text += "#L0#开始强化#l\r\n\r\n";
        cm.sendSimple(text);
    } else {
        cm.sendOk(text);
    }
}

function 获取废弃副本完成次数() {
    return cm.getPQEnteredCount(1) || 0;
}

function do强化() {
    // 1. 再次检查今日是否已强化，防止玩家通过特殊方式绕过主界面检查
    if (是否已强化过()) {
        cm.sendOk("你今天已经强化过了，请明天再来！");
        cm.dispose();
        return;
    }
    // 2. 检查装备栏第一格是否有目标装备（修正索引为0）
    var equip = cm.getInventory(1).getItem(1);
    if (equip === null || equip.getItemId() !== 强化目标项链Id) {
        let tip;
        if (equip == null) {
            tip = `装备栏第一格没有装备，无法进行强化！\r\n\r\n`;
        } else {
            tip = `装备栏第一格是#v${equip.getItemId()}##t${equip.getItemId()}#，无法进行强化！\r\n\r\n`;
        }
        tip += `第一格必须是#v${强化目标项链Id}##t${强化目标项链Id}#，才能强化！`;
        cm.sendOk(tip);
        cm.dispose();
        return;
    }

    // 3. 强化装备全属性+1
    equip.setStr(equip.getStr() + 1);
    equip.setDex(equip.getDex() + 1);
    equip.setInt(equip.getInt() + 2);
    equip.setLuk(equip.getLuk() + 1);
    equip.setHp(equip.getHp() + 2);
    equip.setMp(equip.getMp() + 2);
    equip.setWatk(equip.getWatk() + 1);
    equip.setMatk(equip.getMatk() + 2);
    equip.setWdef(equip.getWdef() + 1);
    equip.setMdef(equip.getMdef() + 1);

    // 4. 通知客户端刷新装备显示
    var player = cm.getPlayer();
    player.equipChanged();
    player.forceUpdateItem(equip);
    // 5. 将强化后的装备信息更新到数据库
    // cm.updateEquip(equip);
    // 6. 关键：设置“今日已强化”标志
    保存强化状态();
    // 8. 发送强化成功提示
    cm.sendOk(`恭喜你！#v${强化目标项链Id}##t${强化目标项链Id}##n每日强化成功`);
    sendSuperMegaphone(player, "每日强化", `恭喜玩家${player.getName()}完成每日精灵吊坠强化!`)
    cm.dispose();
}

function 是否已强化过() {
    return cm.getAccountExtendValue(精灵项链强化key, true) === 已强化值;
}

function 保存强化状态() {
    cm.saveOrUpdateAccountExtendValue(精灵项链强化key, 已强化值, true);
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
