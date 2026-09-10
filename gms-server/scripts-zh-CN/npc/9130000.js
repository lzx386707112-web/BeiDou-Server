var QUEST_ID = -8055;
var NPC_ID = 9130000;
var TICKET = 4000697;
var Quest = Java.type("org.gms.server.quest.Quest");

var status = -1;

function mobList() {
    return (
        "枫叶丘陵田野里的织田残党太多了。去击杀以下怪物各#r200#k只：\r\n\r\n" +
        "#b#o9421511##k\r\n" +
        "#b#o9421512##k\r\n" +
        "#b#o9421513##k\r\n" +
        "#b#o9421514##k\r\n\r\n" +
        "完成后我会给你#b#t" + TICKET + "##k。"
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
            quest.complete(player, NPC_ID);
            cm.sendOk("干得漂亮。拿好#b#t" + TICKET + "##k，去秘密祭坛的光洞进入森兰丸地盘。");
            cm.dispose();
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
    quest.start(player, NPC_ID);
    cm.sendOk("去枫叶丘陵田野清剿织田残党，打完再回来找我。");
    cm.dispose();
}
