var PAGE_SIZE = 10;
var PREVIOUS_PAGE = 1000000;
var NEXT_PAGE = 1000001;
var BACK_TO_TREND_FRONT = 1000002;
var InventoryType = Java.type("org.gms.client.inventory.InventoryType");

var stage = "list";
var currentPage = 0;
var selectedMountIndex = -1;
var mountPairs = [
    [1902000, 1912000], [1902001, 1912000], [1902002, 1912000], [1902004, 1912002],
    [1902005, 1912005], [1902006, 1912005], [1902007, 1912005], [1902008, 1912003],
    [1902009, 1912004], [1902010, 1912006], [1902011, 1912007], [1902012, 1912008],
    [1902013, 1912009], [1902014, 1912010], [1902015, 1912011], [1902016, 1912011],
    [1902017, 1912011], [1902018, 1912011], [1902019, 1912012], [1902020, 1912013],
    [1902021, 1912014], [1902022, 1912015], [1902023, 1912016], [1902028, 1912021],
    [1902031, 1912024], [1902033, 1912026], [1902034, 1912027], [1902036, 1912029],
    [1902037, 1912030], [1902038, 1912031], [1902039, 1912032], [1902045, 1912038],
    [1902047, 1912040], [1902048, 1912041], [1902059, 1912052], [1902060, 1912053],
    [1902401, 1912401], [1902403, 1912403]
];

function start() {
    showMountPage();
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }

    if (stage === "list") {
        handleMountSelection(selection);
        return;
    }
    if (stage === "confirm") {
        claimMount();
        return;
    }
    cm.dispose();
}

function showMountPage() {
    var pageCount = Math.ceil(mountPairs.length / PAGE_SIZE);
    if (currentPage < 0 || currentPage >= pageCount) {
        rejectInvalidSelection();
        return;
    }

    var startIndex = currentPage * PAGE_SIZE;
    var endIndex = Math.min(startIndex + PAGE_SIZE, mountPairs.length);
    var text = "#e坐骑领取#n  #d第 " + (currentPage + 1) + "/" + pageCount + " 页#k\r\n";
    text += "免费领取坐骑和配套鞍具，装备等级限制保持不变。\r\n\r\n";
    for (var i = startIndex; i < endIndex; i++) {
        var pair = mountPairs[i];
        var owned = hasItem(pair[0]) && hasItem(pair[1]) ? " #r[已拥有]#k" : "";
        text += "#L" + i + "##i" + pair[0] + "# #b#z" + pair[0] + "##k" + owned + "#l\r\n";
    }
    if (currentPage > 0) {
        text += "#L" + PREVIOUS_PAGE + "##b上一页#k#l  ";
    }
    if (currentPage + 1 < pageCount) {
        text += "#L" + NEXT_PAGE + "##b下一页#k#l  ";
    }
    text += "#L" + BACK_TO_TREND_FRONT + "##d返回潮流前线#k#l";
    cm.sendSimple(text);
}

function handleMountSelection(selection) {
    var pageCount = Math.ceil(mountPairs.length / PAGE_SIZE);
    if (selection === PREVIOUS_PAGE && currentPage > 0) {
        currentPage--;
        showMountPage();
        return;
    }
    if (selection === NEXT_PAGE && currentPage + 1 < pageCount) {
        currentPage++;
        showMountPage();
        return;
    }
    if (selection === BACK_TO_TREND_FRONT) {
        cm.dispose();
        cm.openNpc(9900009);
        return;
    }

    var startIndex = currentPage * PAGE_SIZE;
    var endIndex = Math.min(startIndex + PAGE_SIZE, mountPairs.length);
    if (selection < startIndex || selection >= endIndex) {
        rejectInvalidSelection();
        return;
    }
    if (!isMountAllowedForJob(mountPairs[selection][0])) {
        cm.sendOk("当前职业不能使用这个坐骑。");
        cm.dispose();
        return;
    }
    if (getRidingSkillId() === 0) {
        cm.sendOk("当前职业暂未配置可用的骑兽技能。");
        cm.dispose();
        return;
    }

    selectedMountIndex = selection;
    stage = "confirm";
    var pair = mountPairs[selectedMountIndex];
    var text = "确定免费领取以下坐骑和配套鞍具吗？\r\n\r\n";
    text += "#i" + pair[0] + "# #b#z" + pair[0] + "##k\r\n";
    text += "#i" + pair[1] + "# #b#z" + pair[1] + "##k";
    cm.sendYesNo(text);
}

function claimMount() {
    if (selectedMountIndex < 0 || selectedMountIndex >= mountPairs.length) {
        rejectInvalidSelection();
        return;
    }

    var pair = mountPairs[selectedMountIndex];
    var skillId = getRidingSkillId();
    if (skillId === 0 || !isMountAllowedForJob(pair[0])) {
        rejectInvalidSelection();
        return;
    }

    var missingItems = [];
    if (!hasItem(pair[0])) {
        missingItems.push(pair[0]);
    }
    if (!hasItem(pair[1])) {
        missingItems.push(pair[1]);
    }
    if (cm.getPlayer().getInventory(InventoryType.EQUIP).getNumFreeSlot() < missingItems.length) {
        cm.sendOk("装备栏空间不足，需要空出 #r" + missingItems.length + "#k 个位置。");
        cm.dispose();
        return;
    }

    for (var i = 0; i < missingItems.length; i++) {
        cm.gainItem(missingItems[i], 1);
    }
    cm.teachSkill(skillId, 1, 1, -1);

    if (missingItems.length === 0) {
        cm.sendOk("坐骑和鞍具都已拥有，骑兽技能已补齐。");
    } else {
        cm.sendOk("领取成功。请在装备栏装备坐骑和鞍具后使用骑兽技能。\r\n装备等级不足时，需要达到对应等级后才能装备。");
    }
    cm.dispose();
}

function hasItem(itemId) {
    return cm.getPlayer().getItemQuantity(itemId, true) > 0;
}

function getRidingSkillId() {
    var jobId = cm.getJobId();
    if (jobId < 1000) {
        return 1004;
    }
    if (jobId < 2000) {
        return 10001004;
    }
    if (jobId === 2000 || (jobId >= 2100 && jobId < 2200)) {
        return 20001004;
    }
    return 0;
}

function isMountAllowedForJob(mountId) {
    var jobId = cm.getJobId();
    var isCygnus = jobId >= 1000 && jobId < 2000;
    if (mountId >= 1902000 && mountId <= 1902002) {
        return !isCygnus;
    }
    if (mountId >= 1902005 && mountId <= 1902007) {
        return isCygnus;
    }
    return true;
}

function rejectInvalidSelection() {
    cm.sendOk("选择无效，请重新打开对话。");
    cm.dispose();
}
