/**
 * @description BOSS伤害成长系统：任务、独立BOSS征服、怪物卡共同增加BOSS伤害百分比
 * @author Codex
 */
var BossDamageGrowth = Java.type('org.gms.server.BossDamageGrowth');

var QUEST_ICON = "#fUI/UIWindow.img/QuestIcon/4/0#";
var CARD_ICON = "#fUI/UIWindow.img/MonsterBook/icon/0#";
var BOSS_ICON = "#fUI/UIWindow.img/UserInfo/bossPetCrown#";
var BOSS_KILL_LIMIT = 10;

// 按BOSS强度排序，每只独立封顶10次；满属性合计40%。
var BOSS_DATA = [
    { key: "papulatus", name: "帕普拉图斯", maxBonus: 1.0, mob: 8500002 },
    { key: "scarga", name: "狮熊双王", maxBonus: 1.2, mob: 9420544 },
    { key: "yaoseng", name: "武林妖僧", maxBonus: 1.4, mob: 9600025 },
    { key: "krexel", name: "克雷塞尔", maxBonus: 1.6, mob: 9420522 },
    { key: "zakum", name: "扎昆", maxBonus: 1.8, mob: 8800002 },
    { key: "showa", name: "昭和大头老板", maxBonus: 2.4, mob: 9400300 },
    { key: "horntail", name: "暗黑龙王", maxBonus: 2.6, mob: 8810018 },
    { key: "pinkbean", name: "品克缤", maxBonus: 2.8, mob: 8820001 },
    { key: "tokyo_vergamot", name: "贝尔加莫特", maxBonus: 3.0, mob: 9400265 },
    { key: "tokyo_dunas", name: "都纳斯", maxBonus: 3.2, mob: 9400270 },
    { key: "tokyo_nibergen", name: "尼贝隆", maxBonus: 3.4, mob: 9400273 },
    { key: "tokyo_nux", name: "努克斯", maxBonus: 3.6, mob: 9400266 },
    { key: "tokyo_dunas2", name: "再生都纳斯", maxBonus: 3.8, mob: 9400294 },
    { key: "tokyo_aufheben", name: "欧碧拉", maxBonus: 4.0, mob: 9400289 },
    { key: "vonleon", name: "狮子王", maxBonus: 4.2, mob: 8840000 }
];

var status = -1;

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
    if (status == 0) {
        showMain();
    } else if (status == 1 && selection == 1) {
        showBossRecords();
    } else {
        cm.dispose();
    }
}

function showMain() {
    var player = cm.getPlayer();
    var questCount = BossDamageGrowth.getQuestCount(player);
    var cardCount = BossDamageGrowth.getMonsterCardCount(player);
    var questBonus = BossDamageGrowth.getQuestBonusPercent(player);
    var bossBonus = BossDamageGrowth.getBossBonusPercent(player);
    var cardBonus = BossDamageGrowth.getMonsterCardBonusPercent(player);
    var totalBonus = BossDamageGrowth.getBonusPercent(player);

    var text = "#e#d===== BOSS伤害成长 =====#k#n\r\n\r\n";
    text += BOSS_ICON + " 当前属性：#r#eBOSS伤害 +" + formatPercent(totalBonus) + "%#n#k\r\n";
    text += BOSS_ICON + " 满成长属性：#rBOSS伤害 +";
    text += formatPercent(BossDamageGrowth.MAX_BONUS_PERCENT) + "%#k\r\n\r\n";

    text += buildProgress(
        CARD_ICON,
        "任务历练",
        questCount,
        BossDamageGrowth.QUEST_REQUIREMENT,
        questBonus,
        BossDamageGrowth.QUEST_MAX_BONUS_PERCENT
    );
    text += buildProgress(
        CARD_ICON,
        "怪物卡册",
        cardCount,
        BossDamageGrowth.MONSTER_CARD_REQUIREMENT,
        cardBonus,
        BossDamageGrowth.MONSTER_CARD_MAX_BONUS_PERCENT
    );
    text += buildBonusProgress(
        CARD_ICON,
        "BOSS征服",
        bossBonus,
        BossDamageGrowth.BOSS_MAX_BONUS_PERCENT
    );

    text += "\r\n#L1#" + BOSS_ICON + " #b查看BOSS征服图鉴#k#l\r\n";
    text += "\r\t\t\n#d每只BOSS击杀10次满进度#k";
    cm.sendSimple(text);
}

function showBossRecords() {
    var totalBonus = BossDamageGrowth.getBossBonusPercent(cm.getPlayer());
    var text = "#e" + BOSS_ICON + " BOSS征服图鉴#n\r\n";
    text += "#d每只BOSS独立上限10次，属性按强度逐级提高。#k\r\n\r\n";
    text += "#e#bBOSS（累计击杀）　　　　　　 次数　BOSS伤害#k#n\r\n";

    for (var i = 0; i < BOSS_DATA.length; i++) {
        var boss = BOSS_DATA[i];
        var count = getKillCount(boss.key);
        var effectiveCount = Math.min(count, BOSS_KILL_LIMIT);
        var currentBonus = effectiveCount * boss.maxBonus / BOSS_KILL_LIMIT;
        var icon = "#fUI/UIWindow.img/MobGage/Mob/" + boss.mob + "#";
        var label = boss.name + "(" + count + "次)";
        var countText = effectiveCount + "/" + BOSS_KILL_LIMIT;
        var bonusText = "+" + formatPercent(currentBonus) + "%/+" + boss.maxBonus + "%";
        var paddedLabel = padBossLabel(label);
        var paddedCount = padCountColumn(countText);

        text += icon + " #b" + paddedLabel + "#k";
        text += "#d" + paddedCount + "#k";
        text += "#r" + bonusText + "#k\r\n";
    }

    text += "\r\n" + BOSS_ICON + " 当前征服属性：#rBOSS伤害 +";
    text += formatPercent(totalBonus) + "%#k / +";
    text += formatPercent(BossDamageGrowth.BOSS_MAX_BONUS_PERCENT) + "%";
    cm.sendOk(text);
    cm.dispose();
}

function buildProgress(icon, name, current, requirement, bonus, maxBonus) {
    var shown = Math.min(current, requirement);
    var progress = Math.floor(shown * 100 / requirement);
    var text = icon + " #e" + name + "#n：#b" + current + "#k / " + requirement + "\r\n";
    text += "         #rBOSS伤害 +" + formatPercent(bonus) + "%#k / +";
    text += formatPercent(maxBonus) + "%\r\n";
    text += "         #B" + progress + "#\r\n\r\n";
    return text;
}

function buildBonusProgress(icon, name, bonus, maxBonus) {
    var progress = Math.floor(Math.min(bonus, maxBonus) * 100 / maxBonus);
    var text = icon + " #e" + name + "#n：#b征服BOSS进度#k\r\n";
    text += "         #rBOSS伤害 +" + formatPercent(bonus) + "%#k / +";
    text += formatPercent(maxBonus) + "%\r\n";
    text += "         #B" + progress + "#\r\n\r\n";
    return text;
}

function getKillCount(key) {
    var value = parseInt(cm.getCharacterExtendValue("boss_growth_kill_" + key));
    return isNaN(value) ? 0 : Math.max(value, 0);
}

// 客户端字体不是等宽字体，制表符也不是固定表格列。
// 中文名称使用全角空格补齐到6个汉字宽度，击杀次数变化则用半角空格微调。
function padBossLabel(text) {
    var result = text;
    var chineseCount = 0;
    var digitCount = 0;
    for (var i = 0; i < text.length; i++) {
        var code = text.charCodeAt(i);
        if (code > 255) {
            chineseCount++;
        } else if (code >= 48 && code <= 57) {
            digitCount++;
        }
    }
    while (chineseCount < 12) {
        result += "　";
        chineseCount++;
    }
    // 累计次数达到两位数后少补两个窄空格，保持次数列起点不变。
    if (digitCount <= 1) {
        result += "  ";
    }
    return result;
}

function padCountColumn(text) {
    // 0/10占4个字符，10/10占5个字符；两个窄空格约等于一个数字宽度。
    return text.length < 5 ? text + "    " : text + "  ";
}

function formatPercent(value) {
    return Number(value).toFixed(1);
}
