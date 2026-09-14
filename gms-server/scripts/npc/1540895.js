var status = 0;
var expedition;
var expedMembers;
var player;
var em;
const ExpeditionType = Java.type("org.gms.server.expeditions.ExpeditionType");
const exped = ExpeditionType.DAMIEN;
var expedName = "DAMIEN";
var expedBoss = "戴米安";
var expedMap = "世界树顶端";
var list = "你想做什么？#b\r\n\r\n#L1#查看当前远征队成员#l\r\n#L2#开始战斗！#l\r\n#L3#退出远征队#l";

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    player = cm.getPlayer();
    expedition = cm.getExpedition(exped);
    em = cm.getEventManager("DamienBattle");
    if (mode != 1) {
        cm.dispose();
        return;
    }
    if (status == 0) {
        if (player.getLevel() < exped.getMinLevel() || player.getLevel() > exped.getMaxLevel()) {
            cm.sendOk("您不符合与" + expedBoss + "战斗的条件！");
            cm.dispose();
            return;
        }
        if (expedition == null) {
            cm.sendSimple("#e#b<远征：" + expedName + ">#k#n" + em.getProperty("party") + "\r\n\r\n你想组建一个团队来挑战 #r" + expedBoss + "#k 吗？\r\n#b#L1#让我们开始吧！#l\r\n#L2#不，我想再等一会儿...#l");
            status = 1;
            return;
        }
        if (expedition.isLeader(player)) {
            if (expedition.isInProgress()) {
                cm.sendOk("远征已经在进行中。");
                cm.dispose();
                return;
            }
            cm.sendSimple(list);
            status = 2;
            return;
        }
        if (expedition.isRegistering()) {
            if (expedition.contains(player)) {
                cm.sendOk("你已经注册了这次远征。请等待队长开始。");
            } else {
                cm.sendOk(expedition.addMember(cm.getPlayer()));
            }
            cm.dispose();
            return;
        }
        if (expedition.isInProgress() && expedition.contains(player)) {
            var eim = em.getInstance(expedName + player.getClient().getChannel());
            if (eim != null && eim.getIntProperty("canJoin") == 1) {
                eim.registerPlayer(player);
            } else {
                cm.sendOk("战斗已经开始。");
            }
            cm.dispose();
            return;
        }
        cm.sendOk("另一支远征队正在挑战戴米安。");
        cm.dispose();
        return;
    }
    if (status == 1) {
        if (selection != 1) {
            cm.dispose();
            return;
        }
        var res = cm.createExpedition(exped);
        if (res == 0) {
            cm.sendOk("#r戴米安远征#k已经创建。再次与我交谈即可开始战斗。");
        } else if (res > 0) {
            cm.sendOk("今日挑战次数已用完。");
        } else {
            cm.sendOk("创建远征失败，请稍后重试。");
        }
        cm.dispose();
        return;
    }
    if (status == 2) {
        if (selection == 1) {
            cm.sendOk("当前远征队长是 #r" + expedition.getLeader().getName() + "#k。");
            cm.dispose();
            return;
        }
        if (selection == 2) {
            em.setProperty("leader", player.getName());
            em.setProperty("channel", player.getClient().getChannel());
            if (!em.startInstance(expedition)) {
                cm.sendOk("已有队伍正在挑战戴米安。");
            }
            cm.dispose();
            return;
        }
        cm.endExpedition(expedition);
        cm.sendOk("远征已经结束。");
        cm.dispose();
    }
}
