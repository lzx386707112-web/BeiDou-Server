var 偷学技能点key = "偷学技能点";
var 已偷学的技能key = "已偷学的技能";

/**
 * @description 技能偷学脚本
 */
var OldTitle = "\t\t\t\t\t#e#k欢迎来到#r[技能偷学]#k系统#n\t\t\t\t\r\n";
var status = -1;
// 技能数组 [技能ID, 最大等级, 技能名字, 所需偷学技能点]
var 技能 = [
    [2311003, 30, "神圣祈祷", 1],
    [4111001, 30, "聚财术", 1],
    [4211003, 30, "敛财术", 1],
    [5121009, 30, "急速领域", 1],
    [1121002, 30, "稳如泰山", 1],
    [2321005, 30, "圣灵之盾", 1],
    [4121003, 30, "挑衅", 1],
    [2121005, 30, "冰破魔兽", 1],
    [1211009, 30, "防御崩坏", 1],
    [2221006, 30, "链环闪电", 1],
    [2121006, 30, "连环爆破", 1],
    [3121002, 30, "火眼晶晶", 3],
    [1320006, 30, "恶龙附身（仅战士能学）", 2],
];

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else if (mode === -1) {
        status--;
    } else {
        cm.dispose();
        return;
    }

    if (status === 0) {
        // 显示当前拥有的偷学技能点
        let 偷学技能点 = getStealKillCount();
        let text = OldTitle;
        text += `\r\n当前拥有的偷学技能点: #r${偷学技能点}#k\r\n`;
        text += "#b（偷学技能点只有255级后在【职业中心-涅槃】获得）\r\n";
        text += "#k可偷学技能列表：(#r已偷学的技能,重复设置不消耗偷学点#k)\r\n\r\n";

        // 循环生成所有技能选项，已偷学技能显示消耗0点
        for (let i = 0; i < 技能.length; i++) {
            const [skillId, maxLevel, skillName, requiredPoints] = 技能[i];
            const isStolen = isSkillAlreadyStolen(skillId);
            const displayPoints = isStolen ? 0 : requiredPoints;
            if(isStolen){
                text += `#L${i}##s${skillId}# ${skillName} (#b已偷学,重新设置#k)#l\r\n`;
            }else {
                text += `#L${i}##s${skillId}# ${skillName} (所需点数: ${displayPoints})#l\r\n`;
            }

        }
        cm.sendSimple(text);
    } else if (status === 1) {
        // 检查选择是否有效
        if (selection >= 0 && selection < 技能.length) {
            // 保存当前选择的技能索引
            this.selectedSkillIndex = selection;
            const [skillId, , skillName, requiredPoints] = 技能[selection];
            const isStolen = isSkillAlreadyStolen(skillId);

            // 根据是否已偷学显示不同的确认信息
            if (isStolen) {
                cm.sendYesNo(`#b${skillName}#k已偷学过，不消耗偷学点。\r\n是否确认重新获取该技能，并设置到Y按键上？`);
            } else {
                cm.sendYesNo(`是否确认偷学#b${skillName}#k？\r\n需要消耗#r${requiredPoints}#k偷学技能点`);
            }
        } else {
            cm.sendOk("无效的选择，请重新操作。");
            cm.dispose();
        }
    } else if (status === 2) {
        // 处理确认结果（mode=1为确认，0为取消）
        if (mode === 1 && this.selectedSkillIndex !== undefined) {
            学习技能(this.selectedSkillIndex);
        } else {
            cm.sendOk("已取消操作。");
            cm.dispose();
        }
    } else {
        cm.dispose();
    }
}
function 是战士(jobId) {
    return jobId==112||jobId==122||jobId==132
}
/**
 * 学习指定索引的技能
 * @param {number} index - 技能数组索引
 */
function 学习技能(index) {
    const player = cm.getPlayer();
    const [skillId, maxLevel, skillName, requiredPoints] = 技能[index];
    const isStolen = isSkillAlreadyStolen(skillId);
    let message = "";
    var jobId = cm.getPlayer().getJob().getId();
    if(skillId==1320006&&!是战士(jobId)){
        cm.sendOk(`该技能仅限战士偷学`);
        cm.dispose();
        return;
    }
    // 未偷学过的技能需要检查点数
    if (!isStolen) {
        const currentPoints = getStealKillCount();
        if (currentPoints < requiredPoints) {
            cm.sendOk(`偷学#b${skillName}#k需要#r${requiredPoints}#k偷学技能点，当前点数不足！`);
            cm.dispose();
            return;
        }
        // 扣除技能点
        saveStealKillCount(-requiredPoints);
        // 记录已偷学技能
        saveStolenSkill(skillId);
        message = `偷学技能#b${skillName}#k成功！\r\n已消耗#r${requiredPoints}#k偷学技能点\r\n`;
    } else {
        message = `#b${skillName}#k重新获取成功！\r\n`;
    }

    // 执行技能教授
    cm.teachSkill(skillId, maxLevel, maxLevel, -1);
    // 检查技能是否已在其他按键，如有则移除
    player.removeBySkillId(skillId)
    // 无论是否已存在，强制设置到21号按键（Y键）
    player.addSkillToKeyboard(21, skillId);
    //
    cm.sendOk(`${message}技能已设置在#bY#k按键上`);
    cm.dispose();
}

/**
 * 检查技能是否已偷学
 * @param {number} skillId - 技能ID
 * @returns {boolean} 是否已偷学
 */
function isSkillAlreadyStolen(skillId) {
    const stolenSkills = cm.getCharacterExtendValue(已偷学的技能key) || "";
    return stolenSkills.split(",").includes(String(skillId));
}

/**
 * 保存已偷学的技能
 * @param {number} skillId - 技能ID
 */
function saveStolenSkill(skillId) {
    let stolenSkills = cm.getCharacterExtendValue(已偷学的技能key) || "";
    const skillList = stolenSkills ? stolenSkills.split(",") : [];

    // 确保技能ID不重复添加
    if (!skillList.includes(String(skillId))) {
        skillList.push(skillId);
        cm.saveOrUpdateCharacterExtendValue(已偷学的技能key, skillList.join(","));
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