/**
 * 9071000 / mPark_welcome — lobby Spiegelmann.
 * Right-side doors open this NPC with mPark_in00 / mPark_in01 / mPark_in02.
 */

var ExtendUtil = Java.type("org.gms.util.ExtendUtil");
var ExtendType = Java.type("org.gms.constants.string.ExtendType");

var DAILY_TYPE = ExtendType.CHARACTER_EXTEND_DAILY.getType();
var DAILY_LIMIT = 2;
var status = -1;
var em = null;
var region = null;

var REGIONS = {
    mPark_in00: {
        key: "MPARK_BASIC",
        name: "初级园区",
        hint: "原版公园与早期路线",
        courses: [
            [953030000, "苔藓森林"],
            [953040000, "天空森林修炼场"],
            [953050000, "禁忌的时间"],
            [953060000, "海盗团秘密基地"],
            [953070000, "异界的战场"],
            [953080000, "偏僻森林危险区域"],
            [953090000, "隐藏的遗迹"],
            [954000000, "废弃的都市"],
            [954010000, "死亡森林"],
            [954020000, "监视之塔"]
        ]
    },
    mPark_in01: {
        key: "MPARK_MIDDLE",
        name: "中级园区",
        hint: "黄昏佩里昂到神秘河入口",
        courses: [
            [953020000, "自动警卫区域"],
            [954030000, "龙之巢穴"],
            [954040000, "忘却的神殿"],
            [954050000, "骑士团要塞"],
            [954060000, "幽灵峡谷"],
            [954070000, "消逝的旅途"],
            [954080000, "啾啾艾尔兰"],
            [954090000, "梦之都拉契尔恩"],
            [954100000, "神秘森林阿尔卡娜"],
            [954101000, "魔拉斯"],
            [954102000, "艾斯佩拉"]
        ]
    },
    mPark_in02: {
        key: "MPARK_ADVANCED",
        name: "高级园区",
        hint: "神秘河中后期与格兰蒂斯",
        courses: [
            [954103000, "塞拉斯"],
            [954104000, "月之桥"],
            [954105000, "苦痛迷宫"],
            [954106000, "利曼"],
            [954107000, "塞尔尼温"],
            [954108000, "阿尔克斯"],
            [954109000, "奥迪温"],
            [954110000, "桃源境"],
            [954111000, "阿尔特利亚"],
            [954112000, "卡尔西温"],
            [954113000, "塔拉哈特"]
        ]
    }
};

function start() {
    status = -1;
    region = REGIONS[cm.getScriptName()];
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        if (cm.getMapId() != 951000000) {
            cm.sendYesNo("要离开怪物公园吗？");
            return;
        }
        if (region == null) {
            cm.sendOk("请走大厅右边的门进入园区。\r\n#b左门#k 初级、#b中门#k 中级、#b右门#k 高级，最右边是 Extreme。\r\n每个园区每天可进入 #r" + DAILY_LIMIT + "#k 次，次数按门分开计算。");
            cm.dispose();
            return;
        }
        em = cm.getEventManager("MonsterPark");
        if (em == null) {
            cm.sendOk("怪物公园现在无法使用。");
            cm.dispose();
            return;
        }
        var remaining = remainingOf(cm.getPlayer());
        var menu = "这里是#b" + region.name + "#k（" + region.hint + "）。\r\n每条路线 6 关、限时 10 分钟。清完本图全部怪物后走上方传送门。\r\n今日剩余次数：#b" + remaining + "/" + DAILY_LIMIT + "#k\r\n#b";
        for (var i = 0; i < region.courses.length; i++) {
            menu += "#L" + i + "#" + region.courses[i][1] + "#l\r\n";
        }
        cm.sendSimple(menu);
    } else if (status == 1) {
        if (cm.getMapId() != 951000000) {
            cm.warp(951000000, 0);
            cm.dispose();
            return;
        }
        if (region == null || selection < 0 || selection >= region.courses.length) {
            cm.dispose();
            return;
        }
        if (cm.getLevel() < 105) {
            cm.sendOk("需要 105 级才能进入怪物公园。");
            cm.dispose();
            return;
        }
        var blocked = dailyBlockedName();
        if (blocked != null) {
            cm.sendOk(blocked + " 今天在" + region.name + "的次数已经用完（" + DAILY_LIMIT + " 次）。");
            cm.dispose();
            return;
        }
        em = cm.getEventManager("MonsterPark");
        em.setProperty("course", String(region.courses[selection][0]));
        em.setProperty("parkRegion", region.key);
        var started;
        if (cm.getParty() == null) {
            started = em.startInstance(cm.getPlayer());
        } else if (!cm.isLeader()) {
            cm.sendOk("请让队长来选择路线。");
            cm.dispose();
            return;
        } else {
            started = em.startInstance(cm.getParty(), cm.getMap());
        }
        if (!started) {
            cm.sendOk("现在没有空闲的公园房间，请稍后再试。");
        } else {
            consumeDaily();
        }
        cm.dispose();
    }
}

function dailyKey() {
    return region.key;
}

function usedOf(chr) {
    var row = ExtendUtil.getExtendValue(String(chr.getId()), DAILY_TYPE, dailyKey());
    if (row == null) {
        return 0;
    }
    return parseInt(row.getExtendValue(), 10) || 0;
}

function remainingOf(chr) {
    return Math.max(0, DAILY_LIMIT - usedOf(chr));
}

function dailyBlockedName() {
    var members = entrants();
    for (var i = 0; i < members.length; i++) {
        var chr = members[i];
        if (usedOf(chr) >= DAILY_LIMIT) {
            return chr.getName();
        }
    }
    return null;
}

function consumeDaily() {
    var members = entrants();
    for (var i = 0; i < members.length; i++) {
        var chr = members[i];
        ExtendUtil.saveOrUpdateExtendValue(String(chr.getId()), DAILY_TYPE, dailyKey(), String(usedOf(chr) + 1));
    }
}

function entrants() {
    if (cm.getParty() == null) {
        return [cm.getPlayer()];
    }
    var online = cm.getPlayer().getPartyMembersOnSameMap();
    var list = [];
    for (var i = 0; i < online.size(); i++) {
        list.push(online.get(i));
    }
    return list;
}
