/**
 * @description 名牌称号系列选择
 *
 * 入口：其他功能.js -> openNpc("称号系列选择")
 *
 * 客户端 BeiDouSetItemCompat.dll 的 .titles 节内置 9 个系列 × 10 档称号，
 * 具体档位由玩家战力自动决定，玩家在这里只能选择「系列」。
 * 服务端接口：cm.getNameplateSeries() / cm.setNameplateSeries(series)
 * 持久化：Character.nameplateTitleSeries -> 角色扩展表 nameplate_title_series
 * 显示条件：装备了名牌戒指（info/nameTag）时才会广播非 0 状态。
 */

// 系列 id 就是数组下标，必须与客户端 .titles 节的系列顺序严格一致，不要调整顺序
// first/last 用于展示该系列的称号风格范围（玄幻 10 档，其余系列上限 8 档）
var SERIES = [
    { name: "玄幻", first: "乾元玄阶", last: "无敌大帝" },
    { name: "斗罗", first: "魂师", last: "三级神祇" },
    { name: "龙珠", first: "赛亚人", last: "破坏神位" },
    { name: "火影", first: "学院生徒", last: "六道之力" },
    { name: "海贼", first: "海贼新秀", last: "觉醒者" },
    { name: "死神", first: "席官", last: "灵王断片" },
    { name: "鬼灭", first: "鬼杀队员", last: "赫刀觉醒" },
    { name: "咒术", first: "四级术师", last: "领域展开" },
    { name: "英雄学院", first: "无个性者", last: "第一英雄" }
];

var status = -1;

function start() {
    // 显式重置：脚本引擎实例可能被复用，不能依赖 var status 的初值
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        展示系列();
    } else if (status === 1) {
        应用系列(selection);
    } else {
        cm.dispose();
    }
}

function 展示系列() {
    var current = 当前系列();
    var text = "\t\t\t#e#k欢迎来到#r[称号系列]#k系统#n\r\n\r\n";
    text += "当前系列：#b【" + SERIES[current].name + "】#k\r\n";
    text += "称号名字会随战力自动升档，这里只需选择你喜欢的风格。\r\n";
    if (戒指状态() === false) {
        text += "#r[提示] 你没有装备名牌戒指，称号暂时不会显示在名片上。#k\r\n";
    }
    text += "\r\n";

    for (var i = 0; i < SERIES.length; i++) {
        text += "#b#L" + i + "#【" + SERIES[i].name + "】"
            + SERIES[i].first + " ~ " + SERIES[i].last + "#l"
            + (i === current ? "  #r(当前使用)#k" : "")
            + "\r\n\r\n";
    }
    cm.sendSimple(text);
}

function 应用系列(selection) {
    selection = parseInt(selection, 10);
    if (isNaN(selection) || selection < 0 || selection >= SERIES.length) {
        cm.sendOk("无效的选择，请重新打开菜单。");
        cm.dispose();
        return;
    }
    var current = 当前系列();
    if (selection === current) {
        cm.sendOk("你当前已经在使用【" + SERIES[selection].name + "】系列了。");
        cm.dispose();
        return;
    }
    cm.setNameplateSeries(selection);

    var text = "称号系列已切换为 #b【" + SERIES[selection].name + "】#k。\r\n\r\n";
    text += "该系列的称号：" + SERIES[selection].first + " ~ " + SERIES[selection].last + "\r\n";
    text += 戒指状态() === false
        ? "#r装备名牌戒指后称号才会显示在名片上。#k"
        : "称号已即时刷新，其他玩家也能看到你的新称号。";
    cm.sendOk(text);
    cm.dispose();
}

// 服务端对越界值已做钳制，这里再兜一层，避免数组越界
function 当前系列() {
    var s = cm.getNameplateSeries();
    if (s < 0 || s >= SERIES.length) {
        return 0;
    }
    return s;
}

// true = 已装备名牌戒指；false = 未装备；null = 检测失败（此时不做任何提示）
function 戒指状态() {
    try {
        var InventoryType = Java.type("org.gms.client.inventory.InventoryType");
        var ItemInformationProvider = Java.type("org.gms.server.ItemInformationProvider");
        var ii = ItemInformationProvider.getInstance();
        var items = cm.getPlayer().getInventory(InventoryType.EQUIPPED).list().toArray();
        for (var i = 0; i < items.length; i++) {
            if (ii.isNameTagRing(items[i].getItemId())) {
                return true;
            }
        }
        return false;
    } catch (e) {
        return null;
    }
}
