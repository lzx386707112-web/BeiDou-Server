/*
 * 龙神技能面板
 * 统一管理 2331010-2331018，不再通过快捷技能、快速转职、技能全满自动发放。
 */
var status = -1;
var SKILL_LEVEL = 30;
var dragonSkills = [
    {id: 2331010, name: "聖歐尼斯龍", type: "召唤", key: 21, keyName: "Y"},
    {id: 2331011, name: "龍之躍", type: "龙攻击", key: 22, keyName: "22"},
    {id: 2331012, name: "龍之氣息", type: "龙攻击", key: 23, keyName: "23"},
    {id: 2331013, name: "閃雷之捷", type: "融合攻击", key: 24, keyName: "24"},
    {id: 2331014, name: "塵土之躍", type: "融合攻击", key: 25, keyName: "25"},
    {id: 2331015, name: "風之氣息", type: "融合攻击", key: 26, keyName: "26"},
    {id: 2331016, name: "龍之捷VI", type: "六转龙攻击", key: 27, keyName: "27"},
    {id: 2331017, name: "龍之躍VI", type: "六转龙攻击", key: 28, keyName: "28"},
    {id: 2331018, name: "龍之氣息VI", type: "六转龙攻击", key: 29, keyName: "29"}
];

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == 1) {
        status++;
    } else if (mode == -1) {
        cm.dispose();
        return;
    } else {
        status--;
    }

    if (status == 0) {
        showPanel();
    } else if (status == 1) {
        learnAndBindSkill(selection);
    } else {
        cm.dispose();
    }
}

function showPanel() {
    var text = "#e#b龙神技能面板#k#n\r\n\r\n";
    text += "选择技能后会学习并绑定到对应键位，不会互相覆盖。\r\n\r\n";
    for (var i = 0; i < dragonSkills.length; i++) {
        var skill = dragonSkills[i];
        text += "#L" + i + "##s" + skill.id + "# #b" + skill.name + "#k #d[" + skill.type + " / 键" + skill.keyName + "]#k#l\r\n";
    }
    cm.sendSimple(text);
}

function learnAndBindSkill(selection) {
    if (selection < 0 || selection >= dragonSkills.length) {
        cm.dispose();
        return;
    }
    var skill = dragonSkills[selection];
    cm.teachSkill(skill.id, SKILL_LEVEL, SKILL_LEVEL, -1);
    bindSkillToKey(skill.key, skill.id, skill.keyName);
    saveDragonSkill(skill.id);
    cm.sendOk("#s" + skill.id + "# #b" + skill.name + "#k 已学习并绑定到 #r" + skill.keyName + "#k 键。");
    cm.dispose();
}

function bindSkillToKey(keyCode, skillId, keyName) {
    cm.getPlayer().addSkillToKeyboard(keyCode, skillId);
    cm.dropMessage(5, "龙神技能面板：" + keyName + "键已绑定技能 " + skillId + "。");
}

function saveDragonSkill(skillId) {
    var key = "龙神技能面板";
    var saved = cm.getCharacterExtendValue(key) || "";
    var list = saved ? saved.split(",") : [];
    if (list.indexOf(String(skillId)) < 0) {
        list.push(skillId);
        cm.saveOrUpdateCharacterExtendValue(key, list.join(","));
    }
}
