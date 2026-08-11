var TITLE = "\t\t\t\t\t#e#r[魔方洗练]#k#n\r\n\r\n";
var CUBES = [4007000, 4007001, 4007002, 4007003, 4007004, 4007005, 4007006, 4007007];
var status = -1;
var targetEquip = null;
var targetCashId = 0;
var selectedCube = 0;
var pendingRoll = null;

var EquipmentCubeManager = Java.type('org.gms.server.EquipmentCubeManager');

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
        showMenu();
    } else if (status === 1) {
        rollCube(selection);
    } else if (status === 2) {
        finishRoll(selection);
    } else {
        cm.dispose();
    }
}

function showMenu() {
    targetEquip = cm.getInventory(1).getItem(1);
    if (!targetEquip) {
        cm.sendOk(TITLE + "请把需要洗练的装备放在装备栏第一格。");
        cm.dispose();
        return;
    }
    targetCashId = Number(targetEquip.getCashId());
    if (!EquipmentCubeManager.canRoll(targetEquip)) {
        cm.sendOk(TITLE + "该装备的魔方数据异常，为避免损坏属性，本次操作已停止。请联系管理员。");
        cm.dispose();
        return;
    }

    var text = TITLE;
    text += "装备：#v" + targetEquip.getItemId() + "##b#t" + targetEquip.getItemId() + "##k\r\n";
    text += "当前词条：#d" + EquipmentCubeManager.describe(targetEquip) + "#k\r\n\r\n";
    text += "每次都会生成新词条；升阶失败时保持当前强度。\r\n";
    text += "只有黑色魔方可以在新旧词条中选择。\r\n";
    text += "卷轴、星级和装备升级属性不会改变。\r\n\r\n";
    for (var i = 0; i < CUBES.length; i++) {
        var cubeId = CUBES[i];
        var count = cm.getPlayer().getItemQuantity(cubeId, false);
        text += "#L" + cubeId + "##v" + cubeId + "##b#t" + cubeId + "##k x " + count;
        text += "  #d(" + EquipmentCubeManager.cubeSummary(targetEquip, cubeId) + ")#k#l\r\n";
    }
    cm.sendSimple(text);
}

function rollCube(cubeId) {
    if (!EquipmentCubeManager.isCube(cubeId)) {
        cm.sendOk(TITLE + "未知魔方。操作已停止。");
        cm.dispose();
        return;
    }
    if (!sameTarget() || cm.getPlayer().getItemQuantity(cubeId, false) < 1) {
        cm.sendOk(TITLE + "装备位置已变化或魔方数量不足。");
        cm.dispose();
        return;
    }
    if (!EquipmentCubeManager.canUseCube(targetEquip, cubeId)) {
        cm.sendOk(TITLE + "该魔方无法洗练当前潜能强度的装备。请使用上限更高的魔方。");
        cm.dispose();
        return;
    }

    selectedCube = cubeId;
    var oldDescription = EquipmentCubeManager.describe(targetEquip);
    pendingRoll = EquipmentCubeManager.roll(targetEquip, selectedCube);
    cm.gainItem(selectedCube, -1);
    if (!pendingRoll.canKeepOld()) {
        try {
            var current = cm.getInventory(1).getItem(1);
            EquipmentCubeManager.apply(current, pendingRoll);
            cm.getPlayer().forceUpdateItem(current);
            cm.sendOk(TITLE + "已消耗 #v" + selectedCube + "##t" + selectedCube + "# x 1\r\n\r\n"
                + "#b原词条：#k\r\n" + oldDescription + "\r\n\r\n"
                + "#r新词条：#k\r\n" + pendingRoll.description());
        } catch (error) {
            cm.sendOk(TITLE + "#r应用魔方结果失败：#k" + error.message);
        }
        cm.dispose();
        return;
    }

    var text = TITLE;
    text += "已消耗 #v" + selectedCube + "##t" + selectedCube + "# x 1\r\n\r\n";
    text += "#b原词条：#k\r\n" + EquipmentCubeManager.describe(targetEquip) + "\r\n\r\n";
    text += "#r新词条：#k\r\n" + pendingRoll.description() + "\r\n\r\n";
    text += "#L0##b应用新词条#k#l\r\n";
    text += "#L1##d保留原词条#k#l";
    cm.sendSimple(text);
}

function finishRoll(selection) {
    if (selection === 1) {
        cm.sendOk(TITLE + "已保留原词条。魔方已经消耗。");
        cm.dispose();
        return;
    }
    if (selection !== 0 || !sameTarget() || !pendingRoll) {
        cm.sendOk(TITLE + "装备位置已变化，未应用新词条。魔方已经消耗。");
        cm.dispose();
        return;
    }

    try {
        var current = cm.getInventory(1).getItem(1);
        EquipmentCubeManager.apply(current, pendingRoll);
        cm.getPlayer().forceUpdateItem(current);
        cm.sendOk(TITLE + "#b魔方洗练成功！#k\r\n\r\n" + EquipmentCubeManager.describe(current));
    } catch (error) {
        cm.sendOk(TITLE + "#r应用魔方结果失败：#k" + error.message);
    }
    cm.dispose();
}

function sameTarget() {
    var current = cm.getInventory(1).getItem(1);
    return current && targetEquip
        && Number(current.getCashId()) === targetCashId
        && current.getItemId() === targetEquip.getItemId();
}
