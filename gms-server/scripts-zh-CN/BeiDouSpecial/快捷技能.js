/*
脚本：新人福利礼包
作者：SpicyBurgerKing
日期：2024-10-31
备注：北斗开发组
 */

var status;
var Title = "#e注意事项:#r请确保Y按键上没有技能或者其他物品，#b领取后在键盘Y键上自动生成该技能.获取技能后是满级的,因此会各占用二转和三转技能点20点,加技能时会提示技能点不足,可以使用删除二段跳后在加点,加完可以重新学习\r\n";
var 已偷学的技能key = "已偷学的技能";

//Start
function start() {
    status = -1;
    action(1, 0, 0);
}

function 获取更换职业次数() {
    let count = cm.getAccountExtendValue("更换职业次数");
    return Number(count) || 0; // 处理未签到过的情况
}

function action(mode, type, selection) {
    var count = 获取更换职业次数();
    if (CheckStatus(mode)) {
        if (status == 0) {
            let text = Title;
            text += " \r\n";
            text += "#b请选择您要领取的技能";
            text += " \r\n";
            text += " \r\n";
            text += " #s2201002# #L0##r快速移动#n#l\r\n";
            text += " \r\n";
            text += " \r\n";
            text += " #s4111006# #L1##r二段跳#n#l\r\n";
            text += " \r\n";
            text += " \r\n";
            text += " #s2321003# #L5##r强化圣龙#n#l\r\n";
            text += " \r\n";
            text += " \r\n";
            text += "#L2#删除二段跳#n#l\r\n";
            if (count > 0) {
                text += " \r\n";
                text += " #s1007# #L3##r锻造#n#l\r\n";
                text += " \r\n";
                text += " #s1005# #L4##r英雄回声#n#l\r\n";
            }
            cm.sendSimple(text);
        } else if (status == 1) {
            doSelect(selection)
        } else {
            //最后一层对话完继续循环至此，推出结束
            cm.dispose();
        }
    }
}

function doSelect(selection) {
    switch (selection) {
        case 0://瞬移
            getKill(2101002)
            break;
        case 1://二段跳
            getKill(4111006)
            break;
        case 2://删除二段跳
            cm.teachSkill(2101002, 0, 20, -1, true);
            cm.teachSkill(4111006, 0, 20, -1, true);
            cm.sendOk("已将技能瞬移和二段跳重置到0级,可以加技能点了,如需使用技能请重新学习！");
            cm.dispose();
            break;
        case 3://锻造
            getKill(1007)
            break;
        case 4://回声
            getKill(1005)
            break;
        case 5://强化圣龙（玛瑙龙光效）
            getKill(2321003)
            break;
        default:
            cm.dispose();
    }
}


// 获取瞬移
function getKill(killId) {
    cm.teachSkill(killId, 20, 20, -1);
    cm.getPlayer().addSkillToKeyboard(21, killId)
    saveStolenSkill(killId);
    cm.sendOk("恭喜你，获取技能成功！");
    cm.dispose();
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

function CheckStatus(mode) {
    if (mode == -1) {
        cm.dispose();
        return false;
    }

    if (mode == 1) {
        status++;
    } else {
        status--;
    }

    if (status == -1) {
        cm.dispose();
        return false;
    }
    return true;
}
