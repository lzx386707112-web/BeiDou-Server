var status = -1;
var selectedOption = -1;
var selectedTargetJob = null;

var HERO_COIN_ID = 4310060;
var HERO_COIN_MATERIALS = [4251200, 4251201, 4251202];
var CORE_GEMSTONE_ID = 2435719;
var CORE_GEMSTONE_COUNT = 100;
var ADVANCEMENT_LEVEL = 180;
var ADVANCEMENT_MESO = 500000000;
var ADVANCEMENT_CASH = 10000;
var EXPLORER_FIFTH_JOB_ITEM_ID = 2029006;
var EXPLORER_FIFTH_JOB_COMPLETED_KEY = "explorer_fifth_job_completed";
var EXPLORER_FOURTH_JOBS = {
    112: true, 122: true, 132: true,
    212: true, 222: true, 232: true,
    312: true, 322: true,
    412: true, 422: true,
    512: true, 522: true
};
var CYGNUS_FOURTH_JOBS = {
    11: {id: 1112, name: "魂骑士"},
    12: {id: 1212, name: "炎术士"},
    13: {id: 1312, name: "风灵使者"},
    14: {id: 1412, name: "夜行者"},
    15: {id: 1512, name: "奇袭者"}
};

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }

    status++;
    if (status === 0) {
        var jobId = cm.getPlayer().getJob().getId();
        var isExplorer = EXPLORER_FOURTH_JOBS[jobId] === true;
        if (!isExplorer && !cm.getPlayer().isCygnus()) {
            cm.sendOk("当前职业还没开放，你就等吧！");
            cm.dispose();
            return;
        }

        if (isExplorer) {
            cleanupExplorerFifthJobItemIfLocked();
        } else {
            selectedTargetJob = getCygnusFourthJob(jobId);
            if (selectedTargetJob === null) {
                cm.sendOk("请先完成骑士团的一转，再来找我吧！");
                cm.dispose();
                return;
            }
            if (jobId === selectedTargetJob.id) {
                cm.sendOk("小伙子，想碰瓷？");
                cm.dispose();
                return;
            }
        }

        var menu = "#e#b五转女神#k#n\r\n\r\n";
        menu += "#L0##b" + (isExplorer ? "完成冒险家五转" : "完成骑士团四转") + "#k#l\r\n";
        menu += "#L1##b合成英雄币#k#l";
        cm.sendSimple(menu);
        return;
    }

    if (status === 1) {
        var currentJobId = cm.getPlayer().getJob().getId();
        selectedOption = selection;
        if (selectedOption === 0) {
            if (EXPLORER_FOURTH_JOBS[currentJobId] === true) {
                prepareExplorerFifthJob();
            } else {
                cm.sendYesNo(buildAdvancementPrompt());
            }
            return;
        }
        if (selectedOption === 1) {
            cm.sendYesNo(buildCraftPrompt());
            return;
        }
        cm.dispose();
        return;
    }

    if (status === 2) {
        if (selectedOption === 0) {
            var currentJobId = cm.getPlayer().getJob().getId();
            if (EXPLORER_FOURTH_JOBS[currentJobId] === true) {
                unlockExplorerFifthJob();
            } else {
                advanceCygnus();
            }
            return;
        }
        if (selectedOption === 1) {
            craftHeroCoin();
            return;
        }
        return;
    }

    cm.dispose();
}

function prepareExplorerFifthJob() {
    cleanupExplorerFifthJobItemIfLocked();
    if (cm.getPlayer().getLevel() < ADVANCEMENT_LEVEL) {
        cm.sendOk("冒险家五转需要达到 " + ADVANCEMENT_LEVEL + " 级。");
        cm.dispose();
        return;
    }
    if (isExplorerFifthJobCompleted()) {
        grantCompletedExplorerFifthJobItem();
        return;
    }
    cm.sendYesNo(buildExplorerFifthJobPrompt());
}

function isExplorerFifthJobCompleted() {
    return cm.getCharacterExtendValue(EXPLORER_FIFTH_JOB_COMPLETED_KEY) == "1";
}

function cleanupExplorerFifthJobItemIfLocked() {
    if (!isExplorerFifthJobCompleted() && cm.haveItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1)) {
        cm.removeAll(EXPLORER_FIFTH_JOB_ITEM_ID);
    }
}

function grantCompletedExplorerFifthJobItem() {
    if (cm.haveItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1)) {
        cm.sendOk("你已经持有 #i" + EXPLORER_FIFTH_JOB_ITEM_ID + "# #b#t"
            + EXPLORER_FIFTH_JOB_ITEM_ID + "##k，可以把它放到快捷键上使用。");
        cm.dispose();
        return;
    }
    if (!cm.canHold(EXPLORER_FIFTH_JOB_ITEM_ID, 1)) {
        cm.sendOk("消耗栏背包空间不足，请整理后再来。");
        cm.dispose();
        return;
    }
    cm.gainItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1);
    cm.sendOk("已补领 #i" + EXPLORER_FIFTH_JOB_ITEM_ID + "# #b#t"
        + EXPLORER_FIFTH_JOB_ITEM_ID + "##k。把它放到快捷键上即可随时打开五转技能面板。");
    cm.dispose();
}

function buildExplorerFifthJobPrompt() {
    var text = "#e冒险家五转解锁#n\r\n\r\n";
    text += buildAdvancementRequirementsText();
    text += "\r\n满足全部条件后将解锁五转并获得 #i" + EXPLORER_FIFTH_JOB_ITEM_ID + "# #b#t"
        + EXPLORER_FIFTH_JOB_ITEM_ID + "##k，确定要继续吗？";
    return text;
}

function unlockExplorerFifthJob() {
    var jobId = cm.getPlayer().getJob().getId();
    if (EXPLORER_FOURTH_JOBS[jobId] !== true) {
        cm.sendOk("当前职业还没开放，你就等吧！");
        cm.dispose();
        return;
    }
    cleanupExplorerFifthJobItemIfLocked();
    if (isExplorerFifthJobCompleted()) {
        grantCompletedExplorerFifthJobItem();
        return;
    }

    var missing = getMissingAdvancementRequirements();
    if (missing.length > 0) {
        cm.sendOk("尚未满足五转条件：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }
    if (!cm.canHold(EXPLORER_FIFTH_JOB_ITEM_ID, 1)) {
        cm.sendOk("消耗栏背包空间不足，请整理后再来。");
        cm.dispose();
        return;
    }

    deductAdvancementCosts();
    cm.saveOrUpdateCharacterExtendValue(EXPLORER_FIFTH_JOB_COMPLETED_KEY, "1");
    cm.gainItem(EXPLORER_FIFTH_JOB_ITEM_ID, 1);
    cm.sendOk("冒险家五转解锁成功，已获得 #i" + EXPLORER_FIFTH_JOB_ITEM_ID + "# #b#t"
        + EXPLORER_FIFTH_JOB_ITEM_ID + "##k。把它放到快捷键上即可随时打开五转技能面板。");
    cm.dispose();
}

function getCygnusFourthJob(jobId) {
    var branch = Math.floor(jobId / 100);
    return CYGNUS_FOURTH_JOBS[branch] || null;
}

function buildAdvancementPrompt() {
    var text = "#e骑士团四转：#b" + selectedTargetJob.name + "#k#n\r\n\r\n";
    text += buildAdvancementRequirementsText();
    text += "\r\n满足全部条件后将直接完成四转，确定要继续吗？";
    return text;
}

function buildAdvancementRequirementsText() {
    var text = "需要满足以下条件：\r\n";
    text += "等级达到 #r" + ADVANCEMENT_LEVEL + "#k  #d(当前 " + cm.getPlayer().getLevel() + ")#k\r\n";
    text += "#i" + HERO_COIN_ID + "# #b#t" + HERO_COIN_ID + "##k × 1";
    text += "  #d(持有 " + cm.itemQuantity(HERO_COIN_ID) + ")#k\r\n";
    text += "#i" + CORE_GEMSTONE_ID + "# #b#t" + CORE_GEMSTONE_ID + "##k × " + CORE_GEMSTONE_COUNT;
    text += "  #d(持有 " + cm.itemQuantity(CORE_GEMSTONE_ID) + ")#k\r\n";
    text += "金币 #r" + cm.numberWithCommas(ADVANCEMENT_MESO) + "#k";
    text += "  #d(持有 " + cm.numberWithCommas(cm.getMeso()) + ")#k\r\n";
    text += "点券 #r" + cm.numberWithCommas(ADVANCEMENT_CASH) + "#k";
    text += "  #d(持有 " + cm.numberWithCommas(cm.getPlayer().getCashShop().getCash(1)) + ")#k\r\n";
    return text;
}

function getMissingAdvancementRequirements() {
    var missing = [];
    if (cm.getPlayer().getLevel() < ADVANCEMENT_LEVEL) {
        missing.push("等级需要达到 " + ADVANCEMENT_LEVEL + " 级");
    }
    if (!cm.haveItem(HERO_COIN_ID, 1)) {
        missing.push("#i" + HERO_COIN_ID + "# #t" + HERO_COIN_ID + "# × 1");
    }
    if (!cm.haveItem(CORE_GEMSTONE_ID, CORE_GEMSTONE_COUNT)) {
        missing.push("#i" + CORE_GEMSTONE_ID + "# #t" + CORE_GEMSTONE_ID + "# × " + CORE_GEMSTONE_COUNT);
    }
    if (cm.getMeso() < ADVANCEMENT_MESO) {
        missing.push("金币 " + cm.numberWithCommas(ADVANCEMENT_MESO));
    }
    if (cm.getPlayer().getCashShop().getCash(1) < ADVANCEMENT_CASH) {
        missing.push("点券 " + cm.numberWithCommas(ADVANCEMENT_CASH));
    }
    return missing;
}

function deductAdvancementCosts() {
    cm.gainItem(HERO_COIN_ID, -1);
    cm.gainItem(CORE_GEMSTONE_ID, -CORE_GEMSTONE_COUNT);
    cm.gainMeso(-ADVANCEMENT_MESO);
    cm.getPlayer().getCashShop().gainCash(1, -ADVANCEMENT_CASH);
}

function advanceCygnus() {
    var jobId = cm.getPlayer().getJob().getId();
    var targetJob = getCygnusFourthJob(jobId);
    if (!cm.getPlayer().isCygnus() || targetJob === null) {
        cm.sendOk("当前职业还没开放，你就等吧！");
        cm.dispose();
        return;
    }
    if (jobId === targetJob.id) {
        cm.sendOk("小伙子，想碰瓷？");
        cm.dispose();
        return;
    }

    var missing = getMissingAdvancementRequirements();
    if (missing.length > 0) {
        cm.sendOk("尚未满足四转条件：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }

    deductAdvancementCosts();
    cm.changeJobById(targetJob.id);
    cm.sendOk("恭喜你完成骑士团四转，成为#b" + targetJob.name + "#k！");
    cm.dispose();
}

function buildCraftPrompt() {
    var text = "#e合成 #i" + HERO_COIN_ID + "# #b#t" + HERO_COIN_ID + "##k × 1#n\r\n\r\n";
    text += "需要以下材料：\r\n";
    for (var i = 0; i < HERO_COIN_MATERIALS.length; i++) {
        var itemId = HERO_COIN_MATERIALS[i];
        text += "#i" + itemId + "# #b#t" + itemId + "##k × 1";
        text += "  #d(持有 " + cm.itemQuantity(itemId) + ")#k\r\n";
    }
    text += "\r\n确定要合成吗？";
    return text;
}

function craftHeroCoin() {
    var missing = [];
    for (var i = 0; i < HERO_COIN_MATERIALS.length; i++) {
        var itemId = HERO_COIN_MATERIALS[i];
        if (!cm.haveItem(itemId, 1)) {
            missing.push("#i" + itemId + "# #t" + itemId + "# × 1");
        }
    }

    if (missing.length > 0) {
        cm.sendOk("材料不足：\r\n" + missing.join("\r\n"));
        cm.dispose();
        return;
    }
    if (!cm.canHold(HERO_COIN_ID, 1)) {
        cm.sendOk("其他栏背包空间不足，请整理后再来。");
        cm.dispose();
        return;
    }

    for (var materialIndex = 0; materialIndex < HERO_COIN_MATERIALS.length; materialIndex++) {
        cm.gainItem(HERO_COIN_MATERIALS[materialIndex], -1);
    }
    cm.gainItem(HERO_COIN_ID, 1);
    cm.sendOk("合成成功，获得 #i" + HERO_COIN_ID + "# #b#t" + HERO_COIN_ID + "##k × 1。");
    cm.dispose();
}
