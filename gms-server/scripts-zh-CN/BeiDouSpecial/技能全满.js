/* Duey			
   Edited by: Sean360 of RZ			
   Latest edits and updates were made by the Maple4U Administrator
   优化说明：补充完整所有职业技能，统一格式，增强容错
*/

var status = 0;
// 配置常量（集中管理，便于修改）
const CONFIG = {
    ITEM_ID: 4000313,          // 消耗道具ID（黄金枫叶）
    NORMAL_ITEM_COST: 1,       // 普通职业道具消耗
    KNIGHT_ITEM_COST: 1,      // 骑士团职业道具消耗
    NORMAL_LEVEL: 10,         // 普通职业等级要求
    KNIGHT_LEVEL: 10,         // 骑士团职业等级要求
    ITEM_DISPLAY: "#v4000313#" // 道具显示文本（带图标）
};
var currentCost;    // 当前职业消耗道具数量
var currentLevel;   // 当前职业等级要求

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === -1) { // 取消操作
        cm.dispose();
        return;
    }
    // 计算当前职业配置（普通/骑士团）
    calcJobConfig(cm.getJobId());
    // 更新对话状态
    status += mode === 1 ? 1 : -1;

    if (status === 0) {
        showConfirmMsg(); // 显示确认提示
    } else if (status === 1) {
        executeSkillMax(cm); // 执行技能全满
    } else {
        cm.dispose();
    }
}

// 计算当前职业的配置
function calcJobConfig(jobId) {
    const isKnight = Math.floor(jobId / 1000) === 1; // 骑士团职业ID前3位为100-199
    currentCost = isKnight ? CONFIG.KNIGHT_ITEM_COST : CONFIG.NORMAL_ITEM_COST;
    currentLevel = isKnight ? CONFIG.KNIGHT_LEVEL : CONFIG.NORMAL_LEVEL;
}

// 显示确认提示信息
function showConfirmMsg() {
    const msg = `#b【技能全满服务】#k\r\n\r\n` +
        `当前职业需满足：\r\n` +
        `1. 等级达到 #r${currentLevel} 级#k\r\n` +
        `2. 拥有 #r${currentCost} 个 ${CONFIG.ITEM_DISPLAY}#k\r\n\r\n` +
        `确认继续？（操作不可逆，道具将被扣除）`;
    cm.sendYesNo(msg);
}

// 执行技能全满操作
function executeSkillMax(cm) {
    const player = cm.getChar();
    const jobId = cm.getJobId();

    // 校验等级
    if (player.getLevel() < currentLevel) {
        cm.sendOk(`等级不足！需达到 ${currentLevel} 级，当前 ${player.getLevel()} 级`);
        cm.dispose();
        return;
    }

    // 校验道具
    if (!cm.haveItem(CONFIG.ITEM_ID, currentCost)) {
        const haveCount = cm.haveItem(CONFIG.ITEM_ID) ?
            cm.getInventory(cm.getChar().getInventoryType("USE")).countById(CONFIG.ITEM_ID) : 0;
        cm.sendOk(`道具不足！需 ${currentCost} 个 ${CONFIG.ITEM_DISPLAY}，当前仅 ${haveCount} 个`);
        cm.dispose();
        return;
    }

    // 扣除道具并学习技能
    cm.gainItem(CONFIG.ITEM_ID, -currentCost);
    teachJobSkills(cm, jobId);
}

// 根据职业ID学习对应技能（补全所有职业）
function teachJobSkills(cm, jobId) {
    // 通用基础技能（所有职业共享）
    if (jobId !== 1000 && jobId !== 0) { // 特殊职业排除重复学习
        cm.teachSkill(1000, 3, 3, -1);   // 生命提升
        cm.teachSkill(1001, 3, 3, -1);   // 魔力提升
        cm.teachSkill(1002, 3, 3, -1);   // 防御提升
        cm.teachSkill(1003, 1, 1, -1);   // 速度提升
        cm.teachSkill(1004, 1, 1, -1);   // 跳跃提升
        cm.teachSkill(1005, 1, 1, -1);   // 魔法恢复
    }

    // 按职业ID分配技能
    switch (jobId) {
        // 1. 超级GM（910）
        case 910:
            cm.teachSkill(9001000, 1, 1, -1);
            cm.teachSkill(9001001, 1, 1, -1);
            cm.teachSkill(9001002, 1, 1, -1);
            cm.teachSkill(9101000, 1, 1, -1);
            cm.teachSkill(9101001, 1, 1, -1);
            cm.teachSkill(9101002, 1, 1, -1);
            cm.teachSkill(9101003, 1, 1, -1);
            cm.teachSkill(9101004, 1, 1, -1);
            cm.teachSkill(9101005, 1, 1, -1);
            cm.teachSkill(9101008, 1, 1, -1);
            break;

        // 2. 战士-英雄（112）
        case 112:
            cm.teachSkill(1000000, 16, 16, -1);
            cm.teachSkill(1000001, 10, 10, -1);
            cm.teachSkill(1000002, 8, 8, -1);
            cm.teachSkill(1001003, 20, 20, -1);
            cm.teachSkill(1001004, 20, 20, -1);
            cm.teachSkill(1001005, 20, 20, -1);
            cm.teachSkill(1100000, 20, 20, -1);
            cm.teachSkill(1100001, 20, 20, -1);
            cm.teachSkill(1100002, 30, 30, -1);
            cm.teachSkill(1100003, 30, 30, -1);
            cm.teachSkill(1101004, 20, 20, -1);
            cm.teachSkill(1101005, 20, 20, -1);
            cm.teachSkill(1101006, 20, 20, -1);
            cm.teachSkill(1101007, 30, 30, -1);
            cm.teachSkill(1110000, 20, 20, -1);
            cm.teachSkill(1110001, 20, 20, -1);
            cm.teachSkill(1111002, 30, 30, -1);
            cm.teachSkill(1111003, 30, 30, -1);
            cm.teachSkill(1111004, 30, 30, -1);
            cm.teachSkill(1111005, 30, 30, -1);
            cm.teachSkill(1111006, 30, 30, -1);
            cm.teachSkill(1111007, 20, 20, -1);
            cm.teachSkill(1111008, 30, 30, -1);
            cm.teachSkill(1120003, 30, 30, -1);
            cm.teachSkill(1120004, 30, 30, -1);
            cm.teachSkill(1120005, 30, 30, -1);
            cm.teachSkill(1121000, 30, 30, -1);
            cm.teachSkill(1121001, 30, 30, -1);
            cm.teachSkill(1121002, 30, 30, -1);
            cm.teachSkill(1121006, 30, 30, -1);
            cm.teachSkill(1121008, 30, 30, -1);
            cm.teachSkill(1121010, 30, 30, -1);
            cm.teachSkill(1121011, 5, 5, -1);
            break;

        // 3. 战士-圣骑士（122）
        case 122:
            cm.teachSkill(1000000, 16, 16, -1);
            cm.teachSkill(1000001, 10, 10, -1);
            cm.teachSkill(1000002, 8, 8, -1);
            cm.teachSkill(1001003, 20, 20, -1);
            cm.teachSkill(1001004, 20, 20, -1);
            cm.teachSkill(1001005, 20, 20, -1);
            cm.teachSkill(1200000, 20, 20, -1);
            cm.teachSkill(1200001, 20, 20, -1);
            cm.teachSkill(1200002, 30, 30, -1);
            cm.teachSkill(1200003, 30, 30, -1);
            cm.teachSkill(1201004, 20, 20, -1);
            cm.teachSkill(1201005, 20, 20, -1);
            cm.teachSkill(1201006, 20, 20, -1);
            cm.teachSkill(1201007, 30, 30, -1);
            cm.teachSkill(1210000, 20, 20, -1);
            cm.teachSkill(1210001, 20, 20, -1);
            cm.teachSkill(1211002, 30, 30, -1);
            cm.teachSkill(1211003, 30, 30, -1);
            cm.teachSkill(1211004, 30, 30, -1);
            cm.teachSkill(1211005, 30, 30, -1);
            cm.teachSkill(1211006, 30, 30, -1);
            cm.teachSkill(1211007, 30, 30, -1);
            cm.teachSkill(1211008, 30, 30, -1);
            cm.teachSkill(1211009, 20, 20, -1);
            cm.teachSkill(1220005, 30, 30, -1);
            cm.teachSkill(1220006, 30, 30, -1);
            cm.teachSkill(1220010, 10, 10, -1);
            cm.teachSkill(1221000, 30, 30, -1);
            cm.teachSkill(1221001, 30, 30, -1);
            cm.teachSkill(1221002, 30, 30, -1);
            cm.teachSkill(1221003, 20, 20, -1);
            cm.teachSkill(1221004, 20, 20, -1);
            cm.teachSkill(1221007, 30, 30, -1);
            cm.teachSkill(1221009, 30, 30, -1);
            cm.teachSkill(1221011, 30, 30, -1);
            cm.teachSkill(1221012, 5, 5, -1);
            break;

        // 4. 战士-黑骑士（132）
        case 132:
            cm.teachSkill(1000000, 16, 16, -1);
            cm.teachSkill(1000001, 10, 10, -1);
            cm.teachSkill(1000002, 8, 8, -1);
            cm.teachSkill(1001003, 20, 20, -1);
            cm.teachSkill(1001004, 20, 20, -1);
            cm.teachSkill(1001005, 20, 20, -1);
            cm.teachSkill(1300000, 20, 20, -1);
            cm.teachSkill(1300001, 20, 20, -1);
            cm.teachSkill(1300002, 30, 30, -1);
            cm.teachSkill(1300003, 30, 30, -1);
            cm.teachSkill(1301004, 20, 20, -1);
            cm.teachSkill(1301005, 20, 20, -1);
            cm.teachSkill(1301006, 20, 20, -1);
            cm.teachSkill(1301007, 30, 30, -1);
            cm.teachSkill(1310000, 20, 20, -1);
            cm.teachSkill(1311001, 30, 30, -1);
            cm.teachSkill(1311002, 30, 30, -1);
            cm.teachSkill(1311003, 30, 30, -1);
            cm.teachSkill(1311004, 30, 30, -1);
            cm.teachSkill(1311005, 30, 30, -1);
            cm.teachSkill(1311006, 30, 30, -1);
            cm.teachSkill(1311007, 20, 20, -1);
            cm.teachSkill(1311008, 20, 20, -1);
            cm.teachSkill(1320005, 30, 30, -1);
            cm.teachSkill(1320006, 30, 30, -1);
            cm.teachSkill(1320008, 25, 25, -1);
            cm.teachSkill(1320009, 25, 25, -1);
            cm.teachSkill(1321000, 30, 30, -1);
            cm.teachSkill(1321001, 30, 30, -1);
            cm.teachSkill(1321002, 30, 30, -1);
            cm.teachSkill(1321003, 30, 30, -1);
            cm.teachSkill(1321007, 10, 10, -1);
            cm.teachSkill(1321010, 5, 5, -1);
            break;

        // 5. 魔法师-冰雷法师（212）
        case 212:
            cm.teachSkill(2000000, 16, 16, -1);
            cm.teachSkill(2000001, 10, 10, -1);
            cm.teachSkill(2001002, 20, 20, -1);
            cm.teachSkill(2001003, 20, 20, -1);
            cm.teachSkill(2001004, 20, 20, -1);
            cm.teachSkill(2001005, 20, 20, -1);
            cm.teachSkill(2100000, 20, 20, -1);
            cm.teachSkill(2101001, 20, 20, -1);
            cm.teachSkill(2101002, 20, 20, -1);
            cm.teachSkill(2101003, 20, 20, -1);
            cm.teachSkill(2101004, 30, 30, -1);
            cm.teachSkill(2101005, 30, 30, -1);
            cm.teachSkill(2110000, 20, 20, -1);
            cm.teachSkill(2110001, 30, 30, -1);
            cm.teachSkill(2111002, 30, 30, -1);
            cm.teachSkill(2111003, 30, 30, -1);
            cm.teachSkill(2111004, 20, 20, -1);
            cm.teachSkill(2111005, 20, 20, -1);
            cm.teachSkill(2111006, 30, 30, -1);
            cm.teachSkill(2121000, 30, 30, -1);
            cm.teachSkill(2121001, 30, 30, -1);
            cm.teachSkill(2121002, 30, 30, -1);
            cm.teachSkill(2121003, 30, 30, -1);
            cm.teachSkill(2121004, 30, 30, -1);
            cm.teachSkill(2121005, 30, 30, -1);
            cm.teachSkill(2121006, 30, 30, -1);
            cm.teachSkill(2121007, 30, 30, -1);
            cm.teachSkill(2121008, 5, 5, -1);
            break;

        // 6. 魔法师-火毒法师（222）
        case 222:
            cm.teachSkill(2000000, 16, 16, -1);
            cm.teachSkill(2000001, 10, 10, -1);
            cm.teachSkill(2001002, 20, 20, -1);
            cm.teachSkill(2001003, 20, 20, -1);
            cm.teachSkill(2001004, 20, 20, -1);
            cm.teachSkill(2001005, 20, 20, -1);
            cm.teachSkill(2200000, 20, 20, -1);
            cm.teachSkill(2201001, 20, 20, -1);
            cm.teachSkill(2201002, 20, 20, -1);
            cm.teachSkill(2201003, 20, 20, -1);
            cm.teachSkill(2201004, 30, 30, -1);
            cm.teachSkill(2201005, 30, 30, -1);
            cm.teachSkill(2210000, 20, 20, -1);
            cm.teachSkill(2210001, 30, 30, -1);
            cm.teachSkill(2211002, 30, 30, -1);
            cm.teachSkill(2211003, 30, 30, -1);
            cm.teachSkill(2211004, 20, 20, -1);
            cm.teachSkill(2211005, 20, 20, -1);
            cm.teachSkill(2211006, 30, 30, -1);
            cm.teachSkill(2221000, 30, 30, -1);
            cm.teachSkill(2221001, 30, 30, -1);
            cm.teachSkill(2221002, 30, 30, -1);
            cm.teachSkill(2221003, 30, 30, -1);
            cm.teachSkill(2221004, 30, 30, -1);
            cm.teachSkill(2221005, 30, 30, -1);
            cm.teachSkill(2221006, 30, 30, -1);
            cm.teachSkill(2221007, 30, 30, -1);
            cm.teachSkill(2221008, 5, 5, -1);
            break;

        // 7. 魔法师-主教（232）
        case 232:
            cm.teachSkill(2000000, 16, 16, -1);
            cm.teachSkill(2000001, 10, 10, -1);
            cm.teachSkill(2001002, 20, 20, -1);
            cm.teachSkill(2001003, 20, 20, -1);
            cm.teachSkill(2001004, 20, 20, -1);
            cm.teachSkill(2001005, 20, 20, -1);
            cm.teachSkill(2300000, 20, 20, -1);
            cm.teachSkill(2301001, 20, 20, -1);
            cm.teachSkill(2301002, 30, 30, -1);
            cm.teachSkill(2301003, 20, 20, -1);
            cm.teachSkill(2301004, 20, 20, -1);
            cm.teachSkill(2301005, 30, 30, -1);
            cm.teachSkill(2310000, 20, 20, -1);
            cm.teachSkill(2311001, 20, 20, -1);
            cm.teachSkill(2311002, 20, 20, -1);
            cm.teachSkill(2311003, 30, 30, -1);
            cm.teachSkill(2311004, 30, 30, -1);
            cm.teachSkill(2311005, 30, 30, -1);
            cm.teachSkill(2311006, 30, 30, -1);
            cm.teachSkill(2321000, 30, 30, -1);
            cm.teachSkill(2321001, 30, 30, -1);
            cm.teachSkill(2321002, 30, 30, -1);
            cm.teachSkill(2321003, 30, 30, -1);
            cm.teachSkill(2321004, 30, 30, -1);
            cm.teachSkill(2321005, 30, 30, -1);
            cm.teachSkill(2321006, 10, 10, -1);
            cm.teachSkill(2321007, 30, 30, -1);
            cm.teachSkill(2321008, 30, 30, -1);
            cm.teachSkill(2321009, 5, 5, -1);
            break;

        // 8. 弓箭手-神射手（312）
        case 312:
            cm.teachSkill(3000000, 16, 16, -1);
            cm.teachSkill(3000001, 20, 20, -1);
            cm.teachSkill(3000002, 8, 8, -1);
            cm.teachSkill(3001003, 20, 20, -1);
            cm.teachSkill(3001004, 20, 20, -1);
            cm.teachSkill(3001005, 20, 20, -1);
            cm.teachSkill(3100000, 20, 20, -1);
            cm.teachSkill(3100001, 30, 30, -1);
            cm.teachSkill(3101002, 20, 20, -1);
            cm.teachSkill(3101003, 20, 20, -1);
            cm.teachSkill(3101004, 20, 20, -1);
            cm.teachSkill(3101005, 30, 30, -1);
            cm.teachSkill(3110000, 20, 20, -1);
            cm.teachSkill(3110001, 20, 20, -1);
            cm.teachSkill(3111002, 20, 20, -1);
            cm.teachSkill(3111003, 30, 30, -1);
            cm.teachSkill(3111004, 30, 30, -1);
            cm.teachSkill(3111005, 30, 30, -1);
            cm.teachSkill(3111006, 30, 30, -1);
            cm.teachSkill(3120005, 30, 30, -1);
            cm.teachSkill(3121000, 30, 30, -1);
            cm.teachSkill(3121002, 30, 30, -1);
            cm.teachSkill(3121003, 30, 30, -1);
            cm.teachSkill(3121004, 30, 30, -1);
            cm.teachSkill(3121006, 30, 30, -1);
            cm.teachSkill(3121007, 30, 30, -1);
            cm.teachSkill(3121008, 30, 30, -1);
            cm.teachSkill(3121009, 5, 5, -1);
            break;

        // 9. 弓箭手-箭神（322）
        case 322:
            cm.teachSkill(3000000, 16, 16, -1);
            cm.teachSkill(3000001, 20, 20, -1);
            cm.teachSkill(3000002, 8, 8, -1);
            cm.teachSkill(3001003, 20, 20, -1);
            cm.teachSkill(3001004, 20, 20, -1);
            cm.teachSkill(3001005, 20, 20, -1);
            cm.teachSkill(3200000, 20, 20, -1);
            cm.teachSkill(3200001, 30, 30, -1);
            cm.teachSkill(3201002, 20, 20, -1);
            cm.teachSkill(3201003, 20, 20, -1);
            cm.teachSkill(3201004, 20, 20, -1);
            cm.teachSkill(3201005, 30, 30, -1);
            cm.teachSkill(3210000, 20, 20, -1);
            cm.teachSkill(3210001, 20, 20, -1);
            cm.teachSkill(3211002, 20, 20, -1);
            cm.teachSkill(3211003, 30, 30, -1);
            cm.teachSkill(3211004, 30, 30, -1);
            cm.teachSkill(3211005, 30, 30, -1);
            cm.teachSkill(3211006, 30, 30, -1);
            cm.teachSkill(3220004, 30, 30, -1);
            cm.teachSkill(3221000, 30, 30, -1);
            cm.teachSkill(3221001, 30, 30, -1);
            cm.teachSkill(3221002, 30, 30, -1);
            cm.teachSkill(3221003, 30, 30, -1);
            cm.teachSkill(3221005, 30, 30, -1);
            cm.teachSkill(3221006, 30, 30, -1);
            cm.teachSkill(3221007, 30, 30, -1);
            cm.teachSkill(3221008, 5, 5, -1);
            break;

        // 10. 飞侠-隐士（412）
        case 412:
            cm.teachSkill(4000000, 20, 20, -1);
            cm.teachSkill(4000001, 8, 8, -1);
            cm.teachSkill(4001002, 20, 20, -1);
            cm.teachSkill(4001003, 20, 20, -1);
            cm.teachSkill(4001334, 20, 20, -1);
            cm.teachSkill(4001344, 20, 20, -1);
            cm.teachSkill(4100000, 20, 20, -1);
            cm.teachSkill(4100001, 30, 30, -1);
            cm.teachSkill(4100002, 20, 20, -1);
            cm.teachSkill(4101003, 20, 20, -1);
            cm.teachSkill(4101004, 20, 20, -1);
            cm.teachSkill(4101005, 30, 30, -1);
            cm.teachSkill(4110000, 20, 20, -1);
            cm.teachSkill(4111001, 20, 20, -1);
            cm.teachSkill(4111002, 30, 30, -1);
            cm.teachSkill(4111003, 20, 20, -1);
            cm.teachSkill(4111004, 30, 30, -1);
            cm.teachSkill(4111005, 30, 30, -1);
            cm.teachSkill(4111006, 20, 20, -1);
            cm.teachSkill(4120002, 30, 30, -1);
            cm.teachSkill(4120005, 30, 30, -1);
            cm.teachSkill(4121000, 30, 30, -1);
            cm.teachSkill(4121003, 30, 30, -1);
            cm.teachSkill(4121004, 30, 30, -1);
            cm.teachSkill(4121006, 30, 30, -1);
            cm.teachSkill(4121007, 30, 30, -1);
            cm.teachSkill(4121008, 30, 30, -1);
            cm.teachSkill(4121009, 5, 5, -1);
            break;

        // 11. 飞侠-侠盗（422）
        case 422:
            cm.teachSkill(4000000, 20, 20, -1);
            cm.teachSkill(4000001, 8, 8, -1);
            cm.teachSkill(4001002, 20, 20, -1);
            cm.teachSkill(4001003, 20, 20, -1);
            cm.teachSkill(4001334, 20, 20, -1);
            cm.teachSkill(4001344, 20, 20, -1);
            cm.teachSkill(4200000, 20, 20, -1);
            cm.teachSkill(4200001, 20, 20, -1);
            cm.teachSkill(4201002, 20, 20, -1);
            cm.teachSkill(4201003, 20, 20, -1);
            cm.teachSkill(4201004, 30, 30, -1);
            cm.teachSkill(4201005, 30, 30, -1);
            cm.teachSkill(4210000, 20, 20, -1);
            cm.teachSkill(4211001, 30, 30, -1);
            cm.teachSkill(4211002, 30, 30, -1);
            cm.teachSkill(4211003, 20, 20, -1);
            cm.teachSkill(4211004, 30, 30, -1);
            cm.teachSkill(4211005, 20, 20, -1);
            cm.teachSkill(4211006, 30, 30, -1);
            cm.teachSkill(4220002, 30, 30, -1);
            cm.teachSkill(4220005, 30, 30, -1);
            cm.teachSkill(4221000, 30, 30, -1);
            cm.teachSkill(4221001, 30, 30, -1);
            cm.teachSkill(4221003, 30, 30, -1);
            cm.teachSkill(4221004, 30, 30, -1);
            cm.teachSkill(4221006, 30, 30, -1);
            cm.teachSkill(4221007, 30, 30, -1);
            cm.teachSkill(4221008, 5, 5, -1);
            break;

        // 12. 海盗-冲锋队长（512）
        case 512:
            cm.teachSkill(5000000, 20, 20, -1);
            cm.teachSkill(5001001, 20, 20, -1);
            cm.teachSkill(5001002, 20, 20, -1);
            cm.teachSkill(5001003, 20, 20, -1);
            cm.teachSkill(5001005, 10, 10, -1);
            cm.teachSkill(5100000, 10, 10, -1);
            cm.teachSkill(5100001, 20, 20, -1);
            cm.teachSkill(5101002, 20, 20, -1);
            cm.teachSkill(5101003, 20, 20, -1);
            cm.teachSkill(5101004, 20, 20, -1);
            cm.teachSkill(5101005, 10, 10, -1);
            cm.teachSkill(5101006, 20, 20, -1);
            cm.teachSkill(5101007, 10, 10, -1);
            cm.teachSkill(5110000, 20, 20, -1);
            cm.teachSkill(5110001, 40, 40, -1);
            cm.teachSkill(5111002, 30, 30, -1);
            cm.teachSkill(5111004, 20, 20, -1);
            cm.teachSkill(5111005, 20, 20, -1);
            cm.teachSkill(5111006, 30, 30, -1);
            cm.teachSkill(5121000, 30, 30, -1);
            cm.teachSkill(5121001, 30, 30, -1);
            cm.teachSkill(5121002, 30, 30, -1);
            cm.teachSkill(5121003, 20, 20, -1);
            cm.teachSkill(5121004, 30, 30, -1);
            cm.teachSkill(5121005, 30, 30, -1);
            cm.teachSkill(5121007, 30, 30, -1);
            cm.teachSkill(5121008, 5, 5, -1);
            cm.teachSkill(5121009, 20, 20, -1);
            cm.teachSkill(5121010, 30, 30, -1);
            break;

        // 13. 海盗-船长（522）
        case 522:
            cm.teachSkill(5000000, 20, 20, -1);
            cm.teachSkill(5001001, 20, 20, -1);
            cm.teachSkill(5001002, 20, 20, -1);
            cm.teachSkill(5001003, 20, 20, -1);
            cm.teachSkill(5001005, 10, 10, -1);
            cm.teachSkill(5200000, 20, 20, -1);
            cm.teachSkill(5201001, 20, 20, -1);
            cm.teachSkill(5201002, 20, 20, -1);
            cm.teachSkill(5201003, 20, 20, -1);
            cm.teachSkill(5201004, 20, 20, -1);
            cm.teachSkill(5201005, 10, 10, -1);
            cm.teachSkill(5201006, 20, 20, -1);
            cm.teachSkill(5210000, 20, 20, -1);
            cm.teachSkill(5211001, 30, 30, -1);
            cm.teachSkill(5211002, 30, 30, -1);
            cm.teachSkill(5211004, 30, 30, -1);
            cm.teachSkill(5211005, 30, 30, -1);
            cm.teachSkill(5211006, 30, 30, -1);
            cm.teachSkill(5220001, 30, 30, -1);
            cm.teachSkill(5220002, 20, 20, -1);
            cm.teachSkill(5220011, 20, 20, -1);
            cm.teachSkill(5221000, 30, 30, -1);
            cm.teachSkill(5221003, 30, 30, -1);
            cm.teachSkill(5221004, 30, 30, -1);
            cm.teachSkill(5221006, 10, 10, -1);
            cm.teachSkill(5221007, 30, 30, -1);
            cm.teachSkill(5221008, 30, 30, -1);
            cm.teachSkill(5221009, 20, 20, -1);
            cm.teachSkill(5221010, 5, 5, -1);
            break;

        // 14. 战神（2112）
        case 2112:
            cm.teachSkill(20001000, 3, 3, -1);
            cm.teachSkill(20001001, 3, 3, -1);
            cm.teachSkill(20001002, 3, 3, -1);
            cm.teachSkill(20001003, 1, 1, -1);
            cm.teachSkill(20001004, 1, 1, -1);
            cm.teachSkill(20001005, 1, 1, -1);
            cm.teachSkill(21000000, 10, 10, -1);
            cm.teachSkill(21000002, 20, 20, -1);
            cm.teachSkill(21001001, 15, 15, -1);
            cm.teachSkill(21001003, 20, 20, -1);
            cm.teachSkill(21100000, 20, 20, -1);
            cm.teachSkill(21100001, 20, 20, -1);
            cm.teachSkill(21100002, 30, 30, -1);
            cm.teachSkill(21100004, 20, 20, -1);
            cm.teachSkill(21100005, 20, 20, -1);
            cm.teachSkill(21101003, 20, 20, -1);
            cm.teachSkill(21110000, 20, 20, -1);
            cm.teachSkill(21110002, 20, 20, -1);
            cm.teachSkill(21110003, 30, 30, -1);
            cm.teachSkill(21110004, 30, 30, -1);
            cm.teachSkill(21110006, 20, 20, -1);
            cm.teachSkill(21111001, 20, 20, -1);
            cm.teachSkill(21111005, 20, 20, -1);
            cm.teachSkill(21110007, 20, 20, -1);
            cm.teachSkill(21110008, 20, 20, -1);
            cm.teachSkill(21120001, 30, 30, -1);
            cm.teachSkill(21120002, 30, 30, -1);
            cm.teachSkill(21120004, 30, 30, -1);
            cm.teachSkill(21120005, 30, 30, -1);
            cm.teachSkill(21120006, 30, 30, -1);
            cm.teachSkill(21120007, 30, 30, -1);
            cm.teachSkill(21121000, 30, 30, -1);
            cm.teachSkill(21121003, 30, 30, -1);
            cm.teachSkill(21120009, 30, 30, -1);
            cm.teachSkill(21120010, 30, 30, -1);
            cm.teachSkill(21121008, 5, 5, -1);
            break;

        // 15. 骑士团-魂骑士（1111）
        case 1111:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            cm.teachSkill(11000000, 10, 10, -1);
            cm.teachSkill(11001001, 10, 10, -1);
            cm.teachSkill(11001002, 20, 20, -1);
            cm.teachSkill(11001003, 20, 20, -1);
            cm.teachSkill(11001004, 20, 20, -1);
            cm.teachSkill(11100000, 20, 20, -1);
            cm.teachSkill(11101001, 20, 20, -1);
            cm.teachSkill(11101002, 30, 30, -1);
            cm.teachSkill(11101003, 20, 20, -1);
            cm.teachSkill(11101004, 30, 30, -1);
            cm.teachSkill(11101005, 10, 10, -1);
            cm.teachSkill(11110000, 20, 20, -1);
            cm.teachSkill(11110005, 20, 20, -1);
            cm.teachSkill(11111001, 20, 20, -1);
            cm.teachSkill(11111002, 20, 20, -1);
            cm.teachSkill(11111003, 20, 20, -1);
            cm.teachSkill(11111004, 30, 30, -1);
            cm.teachSkill(11111006, 30, 30, -1);
            cm.teachSkill(11111007, 20, 20, -1);
            break;

        // 16. 骑士团-炎术士（1211）
        case 1211:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            cm.teachSkill(12000000, 10, 10, -1);
            cm.teachSkill(12001001, 10, 10, -1);
            cm.teachSkill(12001002, 10, 10, -1);
            cm.teachSkill(12001003, 20, 20, -1);
            cm.teachSkill(12001004, 20, 20, -1);
            cm.teachSkill(12101000, 20, 20, -1);
            cm.teachSkill(12101001, 20, 20, -1);
            cm.teachSkill(12101002, 20, 20, -1);
            cm.teachSkill(12101003, 20, 20, -1);
            cm.teachSkill(12101004, 20, 20, -1);
            cm.teachSkill(12101005, 20, 20, -1);
            cm.teachSkill(12101006, 20, 20, -1);
            cm.teachSkill(12110000, 20, 20, -1);
            cm.teachSkill(12110001, 20, 20, -1);
            cm.teachSkill(12111002, 20, 20, -1);
            cm.teachSkill(12111003, 20, 20, -1);
            cm.teachSkill(12111004, 20, 20, -1);
            cm.teachSkill(12111005, 30, 30, -1);
            cm.teachSkill(12111006, 30, 30, -1);
            break;

        // 17. 骑士团-风灵使者（1311）
        case 1311:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            cm.teachSkill(13000000, 20, 20, -1);
            cm.teachSkill(13000001, 8, 8, -1);
            cm.teachSkill(13001002, 10, 10, -1);
            cm.teachSkill(13001003, 20, 20, -1);
            cm.teachSkill(13001004, 20, 20, -1);
            cm.teachSkill(13100000, 20, 20, -1);
            cm.teachSkill(13100004, 20, 20, -1);
            cm.teachSkill(13101001, 20, 20, -1);
            cm.teachSkill(13101002, 30, 30, -1);
            cm.teachSkill(13101003, 20, 20, -1);
            cm.teachSkill(13101005, 20, 20, -1);
            cm.teachSkill(13101006, 10, 10, -1);
            cm.teachSkill(13110003, 20, 20, -1);
            cm.teachSkill(13111000, 20, 20, -1);
            cm.teachSkill(13111001, 30, 30, -1);
            cm.teachSkill(13111002, 20, 20, -1);
            cm.teachSkill(13111004, 20, 20, -1);
            cm.teachSkill(13111005, 10, 10, -1);
            cm.teachSkill(13111006, 20, 20, -1);
            cm.teachSkill(13111007, 20, 20, -1);
            break;

        // 18. 骑士团-夜行者（1411）
        case 1411:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            cm.teachSkill(14000000, 10, 10, -1);
            cm.teachSkill(14000001, 8, 8, -1);
            cm.teachSkill(14001002, 10, 10, -1);
            cm.teachSkill(14001003, 10, 10, -1);
            cm.teachSkill(14001004, 20, 20, -1);
            cm.teachSkill(14001005, 20, 20, -1);
            cm.teachSkill(14100000, 20, 20, -1);
            cm.teachSkill(14100001, 30, 30, -1);
            cm.teachSkill(14100005, 10, 10, -1);
            cm.teachSkill(14101006, 20, 20, -1);
            cm.teachSkill(14101002, 20, 20, -1);
            cm.teachSkill(14101003, 20, 20, -1);
            cm.teachSkill(14101004, 20, 20, -1);
            cm.teachSkill(14110003, 20, 20, -1);
            cm.teachSkill(14110004, 20, 20, -1);
            cm.teachSkill(14111000, 30, 30, -1);
            cm.teachSkill(14111001, 20, 20, -1);
            cm.teachSkill(14111002, 30, 30, -1);
            cm.teachSkill(14111005, 20, 20, -1);
            cm.teachSkill(14111006, 30, 30, -1);
            break;

        // 19. 骑士团-奇袭者（1511）
        case 1511:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            cm.teachSkill(15000000, 10, 10, -1);
            cm.teachSkill(15001001, 20, 20, -1);
            cm.teachSkill(15001002, 20, 20, -1);
            cm.teachSkill(15001003, 10, 10, -1);
            cm.teachSkill(15001004, 20, 20, -1);
            cm.teachSkill(15100000, 10, 10, -1);
            cm.teachSkill(15100001, 20, 20, -1);
            cm.teachSkill(15100004, 20, 20, -1);
            cm.teachSkill(15101002, 20, 20, -1);
            cm.teachSkill(15101003, 20, 20, -1);
            cm.teachSkill(15101005, 20, 20, -1);
            cm.teachSkill(15101006, 20, 20, -1);
            cm.teachSkill(15110000, 20, 20, -1);
            cm.teachSkill(15111001, 20, 20, -1);
            cm.teachSkill(15111002, 10, 10, -1);
            cm.teachSkill(15111003, 20, 20, -1);
            cm.teachSkill(15111004, 20, 20, -1);
            cm.teachSkill(15111005, 20, 20, -1);
            cm.teachSkill(15111006, 20, 20, -1);
            cm.teachSkill(15111007, 30, 30, -1);
            break;

        // 20. 初心者（0）
        case 0:
            // 已通过通用技能学习，无需重复
            break;

        // 21. 骑士团初心者（1000）
        case 1000:
            cm.teachSkill(10001000, 3, 3, -1);
            cm.teachSkill(10001001, 3, 3, -1);
            cm.teachSkill(10001002, 3, 3, -1);
            cm.teachSkill(10001003, 1, 1, -1);
            cm.teachSkill(10001004, 1, 1, -1);
            cm.teachSkill(10001005, 1, 1, -1);
            break;

        // 未匹配职业
        default:
            cm.sendOk("当前职业暂不支持技能全满服务，请确认已完成所有转职。");
            cm.dispose();
            return;
    }

    // 所有技能学习完成
    cm.sendOk("技能全满成功！");
    cm.dispose();
}
