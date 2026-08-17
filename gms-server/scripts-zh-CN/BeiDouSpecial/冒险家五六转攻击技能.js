/*
 * 冒险家五、六转攻击技能学习与键位绑定。
 * 只授予各职业公开的攻击入口，隐藏攻击阶段由服务器回放。
 */
var status = -1;
var selectedOption = -1;
var selectedSkillIndex = -1;
var SKILL_LEVEL = 30;
var ADVANCEMENT_LEVEL = 180;
var EXPLORER_FIFTH_JOB_ITEM_ID = 2029006;
var EXPLORER_FIFTH_JOB_COMPLETED_KEY = "explorer_fifth_job_completed";
var KEY_CODES = [
    30, 48, 46, 32, 18, 33, 34, 35, 23, 36, 37, 38, 50,
    49, 24, 25, 16, 19, 31, 20, 22, 47, 17, 45, 21, 44
];
var KEY_NAMES = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
var KeyBinding = Java.type("org.gms.client.keybind.KeyBinding");
var JOBS = {
    112: {
        name: "英雄",
        skills: Java.type("org.gms.constants.skills.Hero").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [1121001, 1121016, 1121017, 1121018, 1121019, 1121026, 1121027, 1121028, 1121029],
        retiredSkills: [1121001]
    },
    122: {
        name: "圣骑士",
        skills: Java.type("org.gms.constants.skills.Paladin").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [1221013, 1221015, 1221016, 1221018, 1221020, 1221023, 1221025, 1221027, 1221030],
        retiredSkills: [1221013, 1221014, 1221018, 1221019, 1221023, 1221024, 1221025, 1221026]
    },
    132: {
        name: "黑骑士",
        skills: Java.type("org.gms.constants.skills.DarkKnight").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [1321011, 1321012, 1321014, 1321015, 1321017, 1321018, 1321020, 1321022, 1321023, 1321024, 1321025],
        retiredSkills: [1321012, 1321013, 1321014, 1321017, 1321023, 1321024]
    },
    212: {
        name: "火毒大魔导士",
        skills: Java.type("org.gms.constants.skills.FPArchMage").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [2121009, 2121010, 2121011, 2121013, 2121014, 2121015, 2121016, 2121023, 2121024, 2121025, 2121026, 2121027, 2121029, 2121030, 2121031, 2121037],
        retiredSkills: [2121009, 2121010, 2121011, 2121013, 2121014, 2121015, 2121016, 2121023, 2121024, 2121025, 2121026, 2121027, 2121029, 2121030, 2121031, 2121037]
    },
    222: {name: "冰雷大魔导士", skills: Java.type("org.gms.constants.skills.ILArchMage").V_VI_ACTIVE_ATTACKS},
    232: {
        name: "主教",
        skills: Java.type("org.gms.constants.skills.Bishop").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [2321022, 2321023, 2321025, 2321026, 2321027, 2321028, 2321036],
        retiredSkills: [2321022, 2321023, 2321025, 2321026, 2321027, 2321028, 2321036]
    },
    312: {
        name: "箭神",
        skills: Java.type("org.gms.constants.skills.Bowmaster").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [3121011, 3121012, 3121013, 3121014, 3121015, 3121016, 3121020, 3121021, 3121024],
        retiredSkills: [3121011, 3121012, 3121013, 3121014, 3121015, 3121016, 3121020, 3121021, 3121024]
    },
    322: {
        name: "神射手",
        skills: Java.type("org.gms.constants.skills.Marksman").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [3221011, 3221012, 3221014, 3221015, 3221016, 3221017, 3221018, 3221019, 3221020, 3221021, 3221022, 3221023, 3221024, 3221025, 3221026, 3221027, 3221028],
        retiredSkills: [3221011, 3221012, 3221014, 3221015, 3221016, 3221017, 3221018, 3221019, 3221020, 3221021, 3221022, 3221023, 3221024, 3221025, 3221026, 3221027, 3221028]
    },
    412: {
        name: "夜使者",
        skills: Java.type("org.gms.constants.skills.NightLord").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [4121010, 4121012, 4121013, 4121014, 4121015, 4121021],
        retiredSkills: [4121010, 4121012, 4121013, 4121014, 4121015, 4121021]
    },
    422: {
        name: "暗影双刀",
        skills: Java.type("org.gms.constants.skills.Shadower").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [4221013, 4221016, 4221017, 4221024, 4221026, 4221030, 4221031, 4221032, 4221033, 4221036, 4221039],
        retiredSkills: [4221030, 4221031, 4221032, 4221033, 4221034, 4221035, 4221036, 4221037, 4221038, 4221039, 4221040]
    },
    512: {
        name: "拳霸",
        skills: Java.type("org.gms.constants.skills.Buccaneer").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [5121011, 5121012, 5121013, 5121019, 5121020, 5121021, 5121022, 5121023],
        retiredSkills: [5121011, 5121012, 5121013, 5121019, 5121020, 5121021, 5121022, 5121023]
    },
    522: {
        name: "枪神",
        skills: Java.type("org.gms.constants.skills.Corsair").V_VI_ACTIVE_ATTACKS,
        retiredBindings: [5221016, 5221017, 5221018, 5221019, 5221020, 5221021, 5221028, 5221029],
        retiredSkills: [5221016, 5221017, 5221018, 5221019, 5221020, 5221021, 5221028, 5221029]
    }
};

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    status++;
    var job = JOBS[cm.getPlayer().getJob().getId()];
    if (job == null) {
        cm.removeAll(EXPLORER_FIFTH_JOB_ITEM_ID);
        cm.sendOk("当前职业不是支持的冒险家四转职业。");
        cm.dispose();
        return;
    }
    if (!canUseExplorerFifthJobPanel()) {
        cleanupLockedExplorerSkills(job);
        cm.removeAll(EXPLORER_FIFTH_JOB_ITEM_ID);
        cm.sendOk("需要先达到 " + ADVANCEMENT_LEVEL + " 级，并完成五转女神解锁后，才能使用冒险家五、六转技能。");
        cm.dispose();
        return;
    }
    if (status == 0) {
        showMainMenu(job);
    } else if (status == 1) {
        handleMainMenu(job, selection);
    } else if (status == 2) {
        handleSecondStep(job, selection);
    } else if (status == 3) {
        bindSelectedSkill(job, selection);
    } else {
        cm.dispose();
    }
}

function showMainMenu(job) {
    var lastKey = KEY_NAMES.charAt(job.skills.length - 1);
    var text = "#e#b" + job.name + "五、六转攻击技能#k#n\r\n\r\n";
    text += "#L0##b一键学习并按 A-" + lastKey + " 绑定#k#l\r\n";
    text += "#L1##b查看当前职业技能#k#l\r\n";
    text += "#L2##b选择单个技能绑定键位#k#l";
    cm.sendSimple(text);
}

function handleMainMenu(job, selection) {
    selectedOption = selection;
    if (selectedOption == 0) {
        var lastKey = KEY_NAMES.charAt(job.skills.length - 1);
        cm.sendYesNo("将一次学习 " + job.skills.length + " 个可施放攻击技能，并按顺序绑定到 #rA-" +
            lastKey + "#k。\r\n这些字母键上的原有设置会被覆盖，是否继续？");
        return;
    }
    if (selectedOption == 1) {
        showSkillList(job);
        return;
    }
    if (selectedOption == 2) {
        showSkillSelection(job);
        return;
    }
    cm.dispose();
}

function handleSecondStep(job, selection) {
    if (selectedOption == 0) {
        learnAndBindAll(job);
        return;
    }
    if (selectedOption == 2) {
        selectedSkillIndex = selection;
        showKeySelection(job);
        return;
    }
    cm.dispose();
}

function showSkillList(job) {
    var player = cm.getPlayer();
    var text = "#e#b" + job.name + "五、六转攻击技能#k#n\r\n\r\n";
    for (var index = 0; index < job.skills.length; index++) {
        var skillId = Number(job.skills[index]);
        var learned = player.getSkillLevel(skillId) > 0 ? "#g已学习#k" : "#r未学习#k";
        text += "#s" + skillId + "# #b#q" + skillId + "##k #d(" + skillId + ")#k " + learned + "\r\n";
    }
    cm.sendOk(text);
    cm.dispose();
}

function showSkillSelection(job) {
    var text = "#e#b选择要绑定的五、六转技能#k#n\r\n\r\n";
    for (var index = 0; index < job.skills.length; index++) {
        var skillId = Number(job.skills[index]);
        text += "#L" + index + "##s" + skillId + "# #b#q" + skillId + "##k #d(" + skillId + ")#k#l\r\n";
    }
    cm.sendSimple(text);
}

function showKeySelection(job) {
    if (selectedSkillIndex < 0 || selectedSkillIndex >= job.skills.length) {
        cm.dispose();
        return;
    }
    var skillId = Number(job.skills[selectedSkillIndex]);
    var text = "#e#b选择绑定键位#k#n\r\n\r\n";
    text += "#s" + skillId + "# #b#q" + skillId + "##k\r\n\r\n";
    for (var index = 0; index < KEY_CODES.length; index++) {
        text += "#L" + index + "#" + KEY_NAMES.charAt(index) + "#l";
        if ((index + 1) % 6 == 0) {
            text += "\r\n";
        } else {
            text += "  ";
        }
    }
    cm.sendSimple(text);
}

function cleanupRetired(job) {
    var player = cm.getPlayer();
    var retiredBindings = job.retiredBindings || [];
    var retiredSkills = job.retiredSkills || [];
    for (var retiredIndex = 0; retiredIndex < retiredBindings.length; retiredIndex++) {
        player.removeBySkillId(retiredBindings[retiredIndex]);
    }
    for (var skillIndex = 0; skillIndex < retiredSkills.length; skillIndex++) {
        player.removeSkillById(retiredSkills[skillIndex]);
    }
}

function canUseExplorerFifthJobPanel() {
    return cm.getPlayer().getLevel() >= ADVANCEMENT_LEVEL &&
        cm.getCharacterExtendValue(EXPLORER_FIFTH_JOB_COMPLETED_KEY) == "1";
}

function cleanupLockedExplorerSkills(job) {
    var player = cm.getPlayer();
    for (var index = 0; index < job.skills.length; index++) {
        var skillId = Number(job.skills[index]);
        player.removeBySkillId(skillId);
        player.removeSkillById(skillId);
    }
    player.sendKeymap();
}

function learnAndBindAll(job) {
    var player = cm.getPlayer();
    var mappings = [];
    cleanupRetired(job);
    for (var index = 0; index < job.skills.length; index++) {
        var skillId = Number(job.skills[index]);
        cm.teachSkill(skillId, SKILL_LEVEL, SKILL_LEVEL, -1, true);
        player.removeBySkillId(skillId);
        player.changeKeybinding(KEY_CODES[index], new KeyBinding(1, skillId));
        mappings.push(KEY_NAMES.charAt(index) + ": #s" + skillId + "# #q" + skillId + "#");
    }
    player.sendKeymap();
    cm.sendOk("#e#b" + job.name + "技能学习完成#k#n\r\n\r\n" + mappings.join("\r\n"));
    cm.dispose();
}

function bindSelectedSkill(job, keyIndex) {
    if (selectedSkillIndex < 0 || selectedSkillIndex >= job.skills.length ||
        keyIndex < 0 || keyIndex >= KEY_CODES.length) {
        cm.dispose();
        return;
    }
    var player = cm.getPlayer();
    var skillId = Number(job.skills[selectedSkillIndex]);
    cleanupRetired(job);
    cm.teachSkill(skillId, SKILL_LEVEL, SKILL_LEVEL, -1, true);
    player.removeBySkillId(skillId);
    player.changeKeybinding(KEY_CODES[keyIndex], new KeyBinding(1, skillId));
    player.sendKeymap();
    cm.sendOk("#s" + skillId + "# #b#q" + skillId + "##k 已学习并绑定到 #r" +
        KEY_NAMES.charAt(keyIndex) + "#k 键。");
    cm.dispose();
}
