/*
脚本：新人福利礼包
作者：SpicyBurgerKing
日期：2024-10-31
备注：北斗开发组
 */

var status;
var textMsg;
var key = "新人福利礼包"
var meso_id = 9999999;
var cash_id = 9999998;

var dailyRewards = [
    { id: meso_id, qty: 100 },//金币单位W
    { id: cash_id, qty: 25000 },//点卷
    { id: 2029001, qty: 1 },//快捷菜单
    { id: 4000325, qty: 1 },//胡罗卜
    { id: 2430033, qty: 10 },//北斗书
];
var item_id = 1122017;


var icon = "#fUI/UIWindow.img/QuestIcon/7/0#";

//Start
function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (CheckStatus(mode)) {
        if (status == 0) {
            //第一层对话
            var strGetText = cm.getAccountExtendValue(key);
            if (strGetText == "已领取") {
                cm.sendOk("您已经领取了新手奖励了。每个账户#r限领一次。#k");
                cm.dispose();
            } else {
                let text = "您确定要领取新手礼包吗？一个账户#r限领一次。#k\r\n\r\n";
                text += "奖励：\r\n\r\n";
                dailyRewards.forEach(reward => {
                    if (reward.id === meso_id) {
                        text += icon + ` × ${reward.qty} W \t \r\n`;
                    } else if (reward.id === cash_id) {
                        text += `点卷 × ${reward.qty} \t \r\n`;
                    } else {
                        text += `#v${reward.id}##t${reward.id}# x ${reward.qty}\r\n`;
                    }
                });
                text += `#v${item_id}##t${item_id}# 5天使用权\r\n`;
                cm.sendAcceptDecline(text);
            }
        } else if (status == 1) {
            //第二层对话
            if (!cm.isNotCanHold(2, 3)) {
                cm.saveOrUpdateAccountExtendValue(key, "已领取");
                dailyRewards.forEach(reward => {
                    if (reward.id === meso_id) {
                        cm.gainMeso(reward.qty * 10000);
                    } else if (reward.id === cash_id) {
                        cm.getPlayer().getCashShop().gainCash(1, reward.qty);//点券
                    } else {
                        cm.gainItem(reward.id, reward.qty);
                    }
                });
                gainEquip(item_id, 8, 8, 10, 8, 50, 50, 5, 8, 1440 * 5);
                sendSuperMegaphone(cm.getPlayer(), "新手福利", `恭喜玩家${cm.getPlayer().getName()}来到冒险岛!`)
                cm.sendOk("恭喜您获得新手奖励，祝您游戏愉快！");
                cm.dispose();
            }
        } else {
            //最后一层对话完继续循环至此，推出结束
            cm.dispose();
        }
    }

}


function CheckStatus(mode) {
    if (mode == -1) {
        cm.dispose();
        return false;
    }

    if (mode == 1) {
        status++;
    } else {
        status--;
    }

    if (status == -1) {
        cm.dispose();
        return false;
    }
    return true;
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
 * @param watk        物理攻击
 * @param matk        魔法攻击
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
function gainEquip(itemId, str, dex, int, luk, hp, mp, watk, matk, time) {
    var chr = cm.getPlayer();
    chr.gainEquip(
        itemId,
        str,
        dex,
        int,
        luk,
        hp,
        mp,
        watk,
        matk,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        time
    );
    chr.message("恭喜你获装备！");
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
