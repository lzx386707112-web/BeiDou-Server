var status = 0;
var expedition;
var expedMembers;
var player;
var em;

const ExpeditionType = Java.type('org.gms.server.expeditions.ExpeditionType');
const PacketCreator = Java.type('org.gms.util.PacketCreator');
const exped = ExpeditionType.KARING;

var expedName = "KaringFinalBattle";
var expedBoss = "咖凌·终局之战";
var eventName = "KaringFinalBattle";
var list = "你想做什么？#b\r\n\r\n#L1#查看当前远征队成员#l\r\n#L2#开始战斗！#l\r\n#L3#解散远征队#l";

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }

    player = cm.getPlayer();
    expedition = cm.getExpedition(exped);
    em = cm.getEventManager(eventName);

    if (status == 0) {
        if (em == null) {
            cm.sendOk("终局之战事件未加载，请完全重启服务端。");
            cm.dispose();
        } else if (player.getLevel() < exped.getMinLevel() || player.getLevel() > exped.getMaxLevel()) {
            cm.sendOk("你不符合挑战 " + expedBoss + " 的等级条件！");
            cm.dispose();
        } else if (expedition == null) {
            cm.sendSimple("#e#b<远征队：" + expedBoss + ">\r\n#k#n" + em.getProperty("party")
                + "\r\n\r\n要组建远征队，从开场开始挑战咖凌吗？"
                + "\r\n#b#L1#组建远征队#l\r\n#L2#暂时不挑战#l");
            status = 1;
        } else if (expedition.isLeader(player)) {
            if (expedition.isInProgress()) {
                cm.sendOk("你的远征队已经开始战斗了。");
                cm.dispose();
            } else {
                cm.sendSimple(list);
                status = 2;
            }
        } else if (expedition.isRegistering()) {
            if (expedition.contains(player)) {
                cm.sendOk("你已经加入远征队，请等待 #r" + expedition.getLeader().getName() + "#k 开始战斗。");
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
                    cm.sendOk("这次终局之战已无法再加入。");
                }
            } else {
                cm.sendOk("另一支远征队正在挑战 " + expedBoss + "。");
            }
            cm.dispose();
        }
    } else if (status == 1) {
        if (selection == 1) {
            expedition = cm.getExpedition(exped);
            if (expedition != null) {
                cm.sendOk("已经有人创建远征队了，请尝试加入他们！");
                cm.dispose();
                return;
            }
            var result = cm.createExpedition(exped);
            if (result == 0) {
                cm.sendOk("#r" + expedBoss + "远征队#k 已创建。\r\n\r\n再次打开本选项，可查看队伍或开始战斗！");
            } else if (result > 0) {
                cm.sendOk("你当前无法创建这支远征队。");
            } else {
                cm.sendOk("创建远征队时发生错误，请稍后重试。");
            }
        } else {
            cm.sendOk("好的，准备好后再来。");
        }
        cm.dispose();
    } else if (status == 2) {
        expedition = cm.getExpedition(exped);
        if (expedition == null) {
            cm.sendOk("无法读取远征队信息。");
            cm.dispose();
            return;
        }

        if (selection == 1) {
            expedMembers = expedition.getMemberList();
            var size = expedMembers.size();
            if (size == 1) {
                cm.sendOk("你是远征队里唯一的成员。");
                cm.dispose();
                return;
            }
            var text = "以下是当前远征队成员（点击成员可将其移出）：\r\n";
            text += "\r\n\t\t1." + expedition.getLeader().getName();
            for (var i = 1; i < size; i++) {
                text += "\r\n#b#L" + (i + 1) + "#" + (i + 1) + ". " + expedMembers.get(i).getValue() + "#l\n";
            }
            cm.sendSimple(text);
            status = 6;
        } else if (selection == 2) {
            var min = exped.getMinSize();
            if (expedition.getMemberList().size() < min) {
                cm.sendOk("远征队至少需要 " + min + " 名玩家登记。");
                cm.dispose();
                return;
            }
            cm.sendOk("远征队即将开始，将从咖凌开场进入正式流程。");
            status = 4;
        } else if (selection == 3) {
            player.getMap().broadcastMessage(PacketCreator.serverNotice(6, expedition.getLeader().getName() + " 解散了咖凌远征队。"));
            cm.endExpedition(expedition);
            cm.sendOk("远征队已解散。");
            cm.dispose();
        }
    } else if (status == 4) {
        expedition = cm.getExpedition(exped);
        em = cm.getEventManager(eventName);
        if (expedition == null || em == null || !em.startInstance(expedition)) {
            cm.sendOk("其他远征队已经开始挑战，或事件暂时无法初始化。");
            cm.dispose();
            return;
        }
        cm.dispose();
    } else if (status == 6) {
        expedition = cm.getExpedition(exped);
        if (expedition == null) {
            cm.dispose();
            return;
        }
        expedMembers = expedition.getMemberList();
        if (selection > 0) {
            var banned = expedMembers.get(selection - 1);
            expedition.ban(banned);
            cm.sendOk("你已将 " + banned.getValue() + " 移出远征队。");
            cm.dispose();
        } else {
            cm.sendSimple(list);
            status = 2;
        }
    }
}
