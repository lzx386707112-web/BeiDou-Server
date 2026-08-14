/*
 * 冒险家五、六转攻击技能学习与键位绑定。
 * 只授予各职业公开的攻击入口，隐藏攻击阶段由服务器回放。
 */
var status = -1;
var SKILL_LEVEL = 30;
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
        cm.sendOk("当前职业不是支持的冒险家四转职业。");
        cm.dispose();
        return;
    }
    if (status == 0) {
        var lastKey = KEY_NAMES.charAt(job.skills.length - 1);
        cm.sendYesNo("#e#b" + job.name + "五、六转攻击技能#k#n\r\n\r\n" +
            "将一次学习 " + job.skills.length + " 个可施放攻击技能，并按顺序绑定到 #rA-" +
            lastKey + "#k。\r\n这些字母键上的原有设置会被覆盖，是否继续？");
    } else if (status == 1) {
        learnAndBind(job);
    }
}

function learnAndBind(job) {
    var player = cm.getPlayer();
    var mappings = [];
    var retiredBindings = job.retiredBindings || [];
    var retiredSkills = job.retiredSkills || [];
    for (var retiredIndex = 0; retiredIndex < retiredBindings.length; retiredIndex++) {
        player.removeBySkillId(retiredBindings[retiredIndex]);
    }
    for (var skillIndex = 0; skillIndex < retiredSkills.length; skillIndex++) {
        player.removeSkillById(retiredSkills[skillIndex]);
    }
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
