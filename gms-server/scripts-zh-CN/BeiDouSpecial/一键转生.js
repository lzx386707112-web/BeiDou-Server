/**
 * 就转涅槃(一键转生)
 */
var needItemId = 4039020;
var needItemCount = 30;
var needItemId2 = 2049115;
var needItemCount2 = 10;
var meso = 5;
var needLevel = 255;
var text
//重生后的等级，由服务器字段控制 rebirth_level
var rebirthLevel = 1;
//重生后是否可以选择职业
var is_change_job = false;
//重生次数
var reborns;
//转生后的职业id, -1代表职业不变
var jobId = 0;

var item_hp_id = 4032170;
var item_mp_id = 4032171;
var item_hp_count = 50;
var item_mp_count = 50;

// 职业配置数组
var 职业 = [
    ["战士", 100, 10, 0],
    ["魔法师", 200, 8, 0],
    ["弓箭手", 300, 10, 0],
    ["飞侠", 400, 10, 0],
    ["海盗", 500, 10, 0],
    ["魂骑士", 1100, 10, 1000],
    ["炎术士", 1200, 10, 1000],
    ["风灵使者", 1300, 10, 1000],
    ["夜行者", 1400, 10, 1000],
    ["奇袭者", 1500, 10, 1000],
    ["战神", 2100, 10, 2000]
];
var icon = "#fUI/UIWindow.img/Quest/icon8/0#";
const GameConfig = Java.type('org.gms.config.GameConfig');
var maxRebornCount; // 最大转生次数

function start() {
    let baseRebirthLevel = GameConfig.getServerInt("rebirth_level");
    rebirthLevel = Math.max(1, baseRebirthLevel); // 确保最低为1级
    rebirthLevel = Math.min(rebirthLevel, cm.getPlayer().getMaxClassLevel()); // 限制不超过职业最大等级
    reborns = cm.getChar().getReborns();
    maxRebornCount = GameConfig.getServerInt("max_reborn_count");


    // 检查涅槃条件
    var level = cm.getLevel();
    var isCan = level >= needLevel && cm.haveItem(needItemId, needItemCount) && cm.haveItem(needItemId2, needItemCount2) && cm.getPlayer().getCashShop().getCash(1) >= getRealMeso();
    // 构建对话文本
    var text = "\t\t\t\t\t#e#k欢迎来到#r[九转涅槃]#k系统#n\t\t\t\t\r\n\r\n";
    text += `#e#k当前已涅槃#e#r${reborns}#k次\r\n\r\n`; // 新增最大次数显示
    text += "#e#b涅槃条件：#e#r\r\n";
    text += `1.等级达到${needLevel}级\r\n`;
    text += `2.涅槃次数小于${maxRebornCount}次\r\n\r\n`;
    text += `3.消耗 #v${needItemId}##e#r x${needItemCount} 个 + ${meso}W点卷 + #v${needItemId2}##e#r x${needItemCount2}#k\r\n\r\n`;
    text += "#b涅槃后：#r\r\n";
    text += `${icon} 等级回到${rebirthLevel}级\r\n`;
    text += `${icon} 每次涅槃装备最大升级次数+5级（最高50级）\r\n`;
    text += `${icon} 获取一点偷学技能点\r\n`;
    text += `${icon} #v${item_hp_id}##t${item_hp_id}# × ${item_hp_count}\r\n`;
    text += `${icon} #v${item_mp_id}##t${item_mp_id}# × ${item_mp_count}\r\n`;

    if (!is_change_job) {
        text += `${icon} 职业不会变更（如需改变职业请使用#e#b[更换职业]#r功能）#k\r\n`;
    }

    // 根据条件显示不同对话
    if (isCan) {
        if (is_change_job) {
            text += "\r\n请从下面选择你要涅槃的职业，涅槃后将会从之前的职业变为您现在选择的职业\r\n";
            for (var i = 0; i < 职业.length; i++) {
                text += `#L${职业[i][1]}##r${职业[i][0]}#k#l\r\n`;
            }
            text += "\r\n您已满足涅槃条件，如需涅槃请点击下一步\r\n";
            cm.sendNextSelectLevel("SelectEnquire", text);
        } else {
            text += "\r\n您已满足涅槃条件，如需涅槃请点击下一步\r\n";
            cm.sendNextLevel("Enquire", text);
        }
    } else {
        text += "\r\n\r\n#e#g您不满足以上涅槃条件,无法涅槃";
        cm.sendOk(text);
        cm.dispose();
    }
}

function getRealMeso() {
    return meso * 10000;
}


function levelSelectEnquire(id) {
    jobId = parseInt(id);
    cm.sendNextLevel("Rebirth", getTipText());
}

function levelEnquire() {
    cm.sendNextLevel("Rebirth", getTipText());
}

function getTipText() {
    let text = `#k您当前已涅槃#r#e${reborns}#n#k次 / 最大${maxRebornCount}次,涅槃后将变成#r#e${rebirthLevel}#n#k级，#r#e确定涅槃吗？`;
    text += "\r\n#b涅槃后：\r\n";
    text += `${icon} 等级回到${rebirthLevel}级\r\n`;
    text += `${icon} 每次涅槃装备最大升级次数+5级\r\n`;
    text += `${icon} 获取一点偷学技能点\r\n`;
    text += `${icon} #v${item_hp_id}##t${item_hp_id}# × ${item_hp_count}\r\n`;
    text += `${icon} #v${item_mp_id}##t${item_mp_id}# × ${item_mp_count}\r\n`;

    if (!is_change_job) {
        text += `${icon} 职业不会变更（如需改变职业请使用#e#b[更换职业]#r功能）#k\r\n`;
    }
    return text;
}

function levelRebirth() {
    // 检查是否已达最大涅槃次数
    if (reborns >= maxRebornCount) {
        cm.sendOk(`已达到最大涅槃次数${maxRebornCount}次，无法继续涅槃！`);
        cm.dispose();
        return;
    }

    // 检查背包空间
    if (cm.isNotCanHold(4)) {  // 检查其他类型背包
        return;
    }

    // 重生
    let isClear = jobId === 0;
    cm.getPlayer().rebirth(false, false, jobId);
    // 重置状态
    cm.resetStats();
    // 装备变更广播
    cm.getPlayer().equipChanged();
    偷学技能点获取();
    cm.gainItem(item_hp_id, item_hp_count);
    cm.gainItem(item_mp_id, item_mp_count);
    //扣除点券
    cm.getPlayer().getCashShop().gainCash(1, -getRealMeso());
    cm.gainItem(needItemId, -needItemCount);
    cm.gainItem(needItemId2, -needItemCount2);
    全服通告();
    cm.sendOk("#r恭喜你，涅槃成功！" + needItemCount);
    cm.dispose();
}

function 全服通告() {
    let tip = `恭喜肝帝大佬[${cm.getPlayer().getName()}]完成第${cm.getChar().getReborns()}次涅槃,恐怖如斯!~`;
    cm.getPlayer().sendFullServerBroadcast(tip);
}

var 偷学技能点key = "偷学技能点";

function 偷学技能点获取() {
    try {
        // 执行偷学技能点增加操作
        saveStealKillCount(1);
        // 移除偷学技能书（ID:2430674）
        // const skillBookId = 2430674;
        // cm.gainItem(skillBookId, -1);
        // 提示用户操作结果
        cm.getPlayer().dropMessage(5, `恭喜你！成功获取一点偷学技能点！当前偷学技能点：${getStealKillCount()}`);
    } catch (e) {
        // 捕获并处理异常
        cm.getPlayer().dropMessage(5, `操作失败：${e.message}`);
        // 打印错误日志便于调试
        console.error("偷学技能点操作异常:", e);
    }
}

/**
 * 获取当前偷学技能点
 * @returns {number} 技能点数量
 */
function getStealKillCount() {
    const num = cm.getCharacterExtendValue(偷学技能点key);
    return Number(num || 0); // 默认为0
}

/**
 * 保存偷学技能点（可增减）
 * @param {number} count - 变动数量（正数增加，负数减少）
 */
function saveStealKillCount(count) {
    const currentCount = getStealKillCount();
    let newCount = currentCount + count;
    newCount = Math.max(newCount, 0); // 确保不小于0
    cm.saveOrUpdateCharacterExtendValue(偷学技能点key, String(newCount));
}