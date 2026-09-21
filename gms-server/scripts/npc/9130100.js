var TICKET = 4000699;
var status = -1;

function start() { status = -1; action(1, 0, 0); }

function action(mode, type, selection) {
    if (mode != 1) { cm.dispose(); return; }
    status++;
    if (status == 0) {
        if (!cm.haveItem(TICKET, 1)) {
            cm.sendOk("挑战浓姬需要#b#t" + TICKET + "##k。完成枫叶丘陵#b#p9130000##k的每日清剿并选择浓姬门票即可获得。");
            cm.dispose();
            return;
        }
        cm.sendYesNo("浓姬盘踞在比叡山本堂深处。要现在前往讨伐吗？");
        return;
    }
    if (!cm.haveItem(TICKET, 1)) {
        cm.sendOk("需要持有#b#t" + TICKET + "##k才能进入。");
        cm.dispose();
        return;
    }
    var em = cm.getEventManager("PrincessNoBattle");
    if (em == null) { cm.sendOk("浓姬讨伐目前无法开启。"); cm.dispose(); return; }
    var started;
    if (cm.getParty() != null) {
        if (!cm.isLeader()) {
            cm.sendOk("请让队长与我对话开启浓姬讨伐。");
            cm.dispose();
            return;
        }
        var eligible = em.getEligibleParty(cm.getParty());
        if (eligible.size() < 1 || eligible.size() > 6) {
            cm.sendOk("队伍成员需要在当前地图，等级达到160级，且队伍人数为1至6人。");
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
