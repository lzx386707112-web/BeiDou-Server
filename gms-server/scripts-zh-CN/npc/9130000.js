var QUEST_ID = -8055;
var NPC_ID = 9130000;
var RANMARU_TICKET = 4000697;
var PRINCESS_NO_TICKET = 4000699;
var Quest = Java.type("org.gms.server.quest.Quest");

var status = -1;
var selectingReward = false;

function mobList() {
    return (
        "枫叶丘陵田野里的织田残党太多了。去击杀以下怪物各#r200#k只：\r\n\r\n" +
        "#b#o9421511##k\r\n" +
        "#b#o9421512##k\r\n" +
        "#b#o9421513##k\r\n" +
        "#b#o9421514##k\r\n\r\n" +
        "完成后可在#b#t" + RANMARU_TICKET + "##k和#b#t" +
        PRINCESS_NO_TICKET + "##k中选择一张。"
    );
}

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    status++;
    var quest = Quest.getInstance(QUEST_ID);
    var player = cm.getPlayer();
    if (status == 0) {
        if (quest.canComplete(player, NPC_ID)) {
            selectingReward = true;
            cm.sendSimple(
                "干得漂亮。请选择一张挑战门票：\r\n" +
                "#b#L0##i" + RANMARU_TICKET + "# #t" + RANMARU_TICKET + "##l\r\n" +
                "#L1##i" + PRINCESS_NO_TICKET + "# #t" + PRINCESS_NO_TICKET + "##l"
            );
            return;
        }
        if (cm.getQuestStatus(QUEST_ID) == 1) {
            cm.sendOk("还没清完田野。继续击杀以下怪物各200只：\r\n#o9421511#\r\n#o9421512#\r\n#o9421513#\r\n#o9421514#");
            cm.dispose();
            return;
        }
        if (quest.canStart(player, NPC_ID)) {
            cm.sendYesNo(mobList());
            return;
        }
        if (cm.isQuestCompleted(QUEST_ID)) {
            cm.sendOk("今天的清剿委托已经完成了，明天再来吧。");
            cm.dispose();
            return;
        }
        cm.sendOk("120级以上才能接受枫叶丘陵的清剿委托。");
        cm.dispose();
        return;
    }
    if (selectingReward) {
        var ticket = selection == 1 ? PRINCESS_NO_TICKET : RANMARU_TICKET;
        if (!quest.canComplete(player, NPC_ID)) {
            cm.sendOk("这个每日委托目前无法完成。");
            cm.dispose();
            return;
        }
        if (!cm.canHold(ticket, 1)) {
            cm.sendOk("请先在其他栏背包中留出一个空位。");
            cm.dispose();
            return;
        }
        quest.complete(player, NPC_ID);
        cm.gainItem(ticket, 1);
        cm.sendOk("已领取#b#t" + ticket + "##k。");
        cm.dispose();
        return;
    }
    quest.start(player, NPC_ID);
    cm.sendOk("去枫叶丘陵田野清剿织田残党，打完再回来找我。");
    cm.dispose();
}
