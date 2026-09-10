var TICKET = 4000697;
var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function tryEnter(eventName, label) {
    var em = cm.getEventManager(eventName);
    if (em == null) {
        cm.sendOk(label + "尚未启用。");
        cm.dispose();
        return;
    }
    if (!cm.haveItem(TICKET, 1)) {
        cm.sendOk("需要持有#b#t" + TICKET + "##k才能进入。");
        cm.dispose();
        return;
    }
    var started;
    if (cm.getParty() != null) {
        if (!cm.isLeader()) {
            cm.sendOk("请让队长选择难度并进入。");
            cm.dispose();
            return;
        }
        started = em.startInstance(cm.getParty(), cm.getPlayer().getMap(), 1);
    } else {
        started = em.startInstance(cm.getPlayer());
    }
    if (!started) {
        cm.sendOk("已有队伍正在挑战，请稍后再试。");
        cm.dispose();
        return;
    }
    cm.gainItem(TICKET, -1);
    cm.dispose();
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    status++;
    var mapId = cm.getMapId();
    if (mapId == 211041700) {
        if (status == 0) {
            cm.sendYesNo("秘密祭坛就在前方。要前往森兰丸的入口吗？");
        } else {
            cm.warp(807300100, 0);
            cm.dispose();
        }
        return;
    }
    if (mapId == 807300100 || mapId == 807300200) {
        if (status == 0) {
            if (!cm.haveItem(TICKET, 1)) {
                cm.sendOk("进入光洞需要#b#t" + TICKET + "##k。完成枫叶丘陵#b#p9130000##k的每日清剿即可获得。");
                cm.dispose();
                return;
            }
            cm.sendSimple("持有门票即可进入森兰丸地盘。请选择挑战模式：\r\n#b#L0#普通模式#l\r\n#L1#困难模式#l");
            return;
        }
        if (selection == 1) {
            tryEnter("RanmaruHardBattle", "困难森兰丸");
        } else {
            tryEnter("RanmaruBattle", "普通森兰丸");
        }
        return;
    }
    cm.sendOk("打倒森兰丸，阻止这场危险的仪式。");
    cm.dispose();
}
