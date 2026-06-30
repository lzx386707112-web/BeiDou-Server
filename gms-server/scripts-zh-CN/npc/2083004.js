/*
    Mark of the Squad - Horntail expedition starter.
*/

var status = 0;
var selectedMode = -1;
var expedition;
var expedMembers;
var player;
var em;

const ExpeditionType = Java.type('org.gms.server.expeditions.ExpeditionType');

var list = "请选择要执行的操作：#b\r\n\r\n#L1#查看当前远征队成员#l\r\n#L2#开始战斗！#l\r\n#L3#解散远征队#l";

var exped;
var expedName;
var expedBoss;
var eventName;

function start() {
    action(1, 0, 0);
}

function configure(mode) {
    selectedMode = mode;
    if (selectedMode == 1) {
        exped = ExpeditionType.CHAOS_HORNTAIL;
        expedName = "ChaosHorntail";
        expedBoss = "进阶暗黑龙王";
        eventName = "ChaosHorntail";
    } else {
        exped = ExpeditionType.HORNTAIL;
        expedName = "Horntail";
        expedBoss = "暗黑龙王";
        eventName = "HorntailBattle";
    }
}

function action(mode, type, selection) {
    player = cm.getPlayer();

    if (mode == -1 || mode == 0) {
        cm.dispose();
        return;
    }

    if (status == 0) {
        cm.sendSimple("请选择你要管理的远征队：#b\r\n\r\n#L0#暗黑龙王#l\r\n#L1#进阶暗黑龙王#l");
        status = 1;
        return;
    }

    if (status == 1) {
        configure(selection);
        expedition = cm.getExpedition(exped);
        em = cm.getEventManager(eventName);

        if (em == null) {
            cm.sendOk("事件初始化失败。");
            cm.dispose();
        } else if (player.getLevel() < exped.getMinLevel() || player.getLevel() > exped.getMaxLevel()) {
            cm.sendOk("你不符合挑战 " + expedBoss + " 的条件！");
            cm.dispose();
        } else if (expedition == null) {
            cm.sendSimple("#e#b<远征队：" + expedBoss + ">\r\n#k#n" + em.getProperty("party") + "\r\n\r\n你要组建队伍挑战 #r" + expedBoss + "#k 吗？\r\n#b#L1#马上开始！#l\r\n#L2#暂时不了，我再等等。#l");
            status = 2;
        } else if (expedition.isLeader(player)) {
            if (expedition.isInProgress()) {
                cm.sendOk("你的远征队已经开始战斗了。");
                cm.dispose();
            } else {
                cm.sendSimple(list);
                status = 3;
            }
        } else if (expedition.isRegistering()) {
            if (expedition.contains(player)) {
                cm.sendOk("你已经加入远征队了。请等待 #r" + expedition.getLeader().getName() + "#k 开始战斗。");
            } else {
                cm.sendOk(expedition.addMember(player));
            }
            cm.dispose();
        } else if (expedition.isInProgress()) {
            if (expedition.contains(player)) {
                var eim = em.getInstance(expedName + player.getClient().getChannel());
                if (eim != null && eim.getIntProperty("canJoin") == 1) {
                    eim.registerPlayer(player);
                } else {
                    cm.sendOk("你的远征队已经开始挑战 " + expedBoss + " 了。");
                }
            } else {
                cm.sendOk("其他远征队已经开始挑战 " + expedBoss + " 了。");
            }
            cm.dispose();
        }
    } else if (status == 2) {
        configure(selectedMode);
        expedition = cm.getExpedition(exped);

        if (selection == 1) {
            if (expedition != null) {
                cm.sendOk("已经有人创建远征队了，请尝试加入他们！");
                cm.dispose();
                return;
            }

            var res = cm.createExpedition(exped);
            if (res == 0) {
                cm.sendOk("#r" + expedBoss + "远征队#k 已创建。\r\n\r\n再次和我对话，可以查看当前队伍或开始战斗！");
            } else if (res > 0) {
                cm.sendOk("抱歉，你今天挑战该远征队的次数已经用完了，请改天再试。");
            } else {
                cm.sendOk("创建远征队时发生未知错误，请稍后再试。");
            }
        } else {
            cm.sendOk("好吧，并不是每个人都准备好挑战 " + expedBoss + "。");
        }
        cm.dispose();
    } else if (status == 3) {
        configure(selectedMode);
        expedition = cm.getExpedition(exped);

        if (selection == 1) {
            if (expedition == null) {
                cm.sendOk("无法读取远征队信息。");
                cm.dispose();
                return;
            }
            expedMembers = expedition.getMemberList();
            var size = expedMembers.size();
            if (size == 1) {
                cm.sendOk("你是远征队里唯一的成员。");
                cm.dispose();
                return;
            }
            var text = "以下是你的远征队成员（点击成员可将其移出远征队）：\r\n";
            text += "\r\n\t\t1." + expedition.getLeader().getName();
            for (var i = 1; i < size; i++) {
                text += "\r\n#b#L" + (i + 1) + "#" + (i + 1) + ". " + expedMembers.get(i).getValue() + "#l\n";
            }
            cm.sendSimple(text);
            status = 6;
        } else if (selection == 2) {
            var min = exped.getMinSize();
            var size = expedition.getMemberList().size();
            if (size < min) {
                cm.sendOk("远征队至少需要 " + min + " 名玩家登记。");
                cm.dispose();
                return;
            }

            cm.sendOk("远征队即将开始，你将被传送去挑战 " + expedBoss + "。");
            status = 4;
        } else if (selection == 3) {
            const PacketCreator = Java.type('org.gms.util.PacketCreator');
            player.getMap().broadcastMessage(PacketCreator.serverNotice(6, expedition.getLeader().getName() + " 解散了远征队。"));
            cm.endExpedition(expedition);
            cm.sendOk("远征队已解散。");
            cm.dispose();
        }
    } else if (status == 4) {
        configure(selectedMode);
        expedition = cm.getExpedition(exped);
        em = cm.getEventManager(eventName);

        if (em == null) {
            cm.sendOk("事件初始化失败。");
            cm.dispose();
            return;
        }

        em.setProperty("leader", player.getName());
        em.setProperty("channel", player.getClient().getChannel());
        if (!em.startInstance(expedition)) {
            cm.sendOk("其他远征队已经开始挑战 " + expedBoss + " 了。");
            cm.dispose();
            return;
        }
        cm.dispose();
    } else if (status == 6) {
        configure(selectedMode);
        expedition = cm.getExpedition(exped);
        expedMembers = expedition.getMemberList();

        if (selection > 0) {
            var banned = expedMembers.get(selection - 1);
            expedition.ban(banned);
            cm.sendOk("你已将 " + banned.getValue() + " 移出远征队。");
            cm.dispose();
        } else {
            cm.sendSimple(list);
            status = 3;
        }
    }
}
