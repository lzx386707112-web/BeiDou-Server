var status = 0;
var page = 0;
var selectedBoss = null;

var FREE_MARKET_ID = 910000000;
var CASINO_SHOP_ID = 9999001;
var PAGE_SIZE = 10;
var BOSS_SPAWN_X = 470;
var BOSS_SPAWN_Y = 34;

var LifeFactory = Java.type("org.gms.server.life.LifeFactory");
var BlackjackDealerBot = Java.type("soloMapling.ArtificialPlayer.BotTypes.Blackjack.BlackjackDealerBot");
var BotBossCombatManager = Java.type("soloMapling.ArtificialPlayer.BotBossCombatManager");
var Point = Java.type("java.awt.Point");

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }

    status++;
    if (status == 0) {
        sendMainMenu();
        return;
    }

    if (status == 1) {
        if (selection == 0) {
            page = 0;
            sendBossPage();
            return;
        }
        if (selection == 1) {
            cm.sendOk(BlackjackDealerBot.joinNearestTable(cm.getPlayer()));
            cm.dispose();
            return;
        }
        if (selection == 2) {
            cm.openShopNPC(CASINO_SHOP_ID);
            cm.dispose();
            return;
        }
        if (selection == 3) {
            cm.sendOk("先加入 21 点桌，然后把筹码丢在自己附近作为下注。\r\n\r\n轮到你行动时，可以在聊天里输入“要牌”或“停牌”。");
            cm.dispose();
            return;
        }
        cm.dispose();
        return;
    }

    if (status == 2) {
        handleBossSelection(selection);
        return;
    }

    if (status == 3) {
        summonSelectedBoss();
        cm.dispose();
        return;
    }

    cm.dispose();
}

function sendMainMenu() {
    var text = "#e自由市场服务#n\r\n\r\n";
    text += "#L0#召唤 Boss#l\r\n";
    text += "#L1#加入最近的 21 点桌#l\r\n";
    text += "#L2#兑换赌场筹码#l\r\n";
    text += "#L3#查看 21 点玩法#l";
    cm.sendSimple(text);
}

function sendBossPage() {
    if (cm.getMapId() != FREE_MARKET_ID) {
        cm.sendOk("请在自由市场入口召唤 Boss。");
        cm.dispose();
        return;
    }

    var bosses = LifeFactory.getBossSummonList();
    if (bosses == null || bosses.size() == 0) {
        cm.sendOk("当前没有可召唤的 Boss。");
        cm.dispose();
        return;
    }

    var maxPage = Math.floor((bosses.size() - 1) / PAGE_SIZE);
    if (page > maxPage) {
        page = maxPage;
    }

    var start = page * PAGE_SIZE;
    var end = Math.min(start + PAGE_SIZE, bosses.size());
    var text = "#e自由市场 Boss 召唤#n\r\n";
    text += "当前页：" + (page + 1) + " / " + (maxPage + 1) + "\r\n";
    text += "Boss 会出现在市场中间偏右位置。Boss 死亡前不能召唤新的。\r\n\r\n";

    for (var i = start; i < end; i++) {
        var boss = bosses.get(i);
        text += "#L" + i + "##b" + bossLabel(boss) + "#k#l\r\n";
    }
    text += "\r\n";
    if (page > 0) {
        text += "#L9000#上一页#l\r\n";
    }
    if (page < maxPage) {
        text += "#L9001#下一页#l\r\n";
    }
    cm.sendSimple(text);
}

function handleBossSelection(selection) {
    var bosses = LifeFactory.getBossSummonList();
    if (selection == 9000) {
        page = Math.max(0, page - 1);
        status = 1;
        sendBossPage();
        return;
    }
    if (selection == 9001) {
        page++;
        status = 1;
        sendBossPage();
        return;
    }
    if (selection < 0 || selection >= bosses.size()) {
        cm.sendOk("这个 Boss 暂时不可召唤。");
        cm.dispose();
        return;
    }

    selectedBoss = bosses.get(selection);
    cm.sendYesNo("确定要召唤 #r" + bossLabel(selectedBoss) + "#k 吗？\r\n\r\n同一时间市场只允许存在一只 Boss。");
}

function summonSelectedBoss() {
    if (selectedBoss == null) {
        cm.sendOk("请选择一个 Boss。");
        return;
    }

    var map = cm.getMap();
    if (map.countBosses() > 0) {
        cm.sendOk("当前市场已经存在 Boss，先击败它再召唤新的。");
        return;
    }

    var monster = LifeFactory.getMonster(selectedBoss.getId());
    if (monster == null || !monster.isBoss() || monster.getMaxHp() <= 0) {
        cm.sendOk("这个 Boss 当前资源不存在，已取消召唤。");
        return;
    }

    map.spawnMonsterOnGroundBelow(monster, new Point(BOSS_SPAWN_X, BOSS_SPAWN_Y));
    BotBossCombatManager.handleChatTrigger(cm.getPlayer(), "假人打boss");
    cm.sendOk("已召唤 #r" + bossLabel(selectedBoss) + "#k。\r\nBoss 会出现在市场中间偏右位置，假人会自动集火。");
}

function bossLabel(boss) {
    return boss.getName() + " [" + boss.getId() + "] Lv." + boss.getLevel() + " HP " + formatNumber(boss.getHp());
}

function formatNumber(value) {
    var str = String(value);
    var out = "";
    while (str.length > 3) {
        out = "," + str.substring(str.length - 3) + out;
        str = str.substring(0, str.length - 3);
    }
    return str + out;
}
