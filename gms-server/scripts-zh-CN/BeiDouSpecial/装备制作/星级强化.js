/**
 * 武器星之力强化。
 * 装备栏第1格必须放入已用完卷轴升级次数的武器。
 */
var status = -1;
var selectedItem = null;
var selectedScrollId = 0;

const InventoryType = Java.type('org.gms.client.inventory.InventoryType');
const InventoryManipulator = Java.type('org.gms.client.inventory.manipulator.InventoryManipulator');
const ItemInformationProvider = Java.type('org.gms.server.ItemInformationProvider');

var SUCCESS = 0;
var FAILURE = 1;
var DESTROYED = 2;
var SAFE_CHECKPOINTS = {10: true, 15: true, 20: true};
var SAFEGUARD_SCROLLS = {
    4260012: 200,
    4260013: 400,
    4260014: 600,
    4260015: 800,
    4260016: 1000,
    4260017: 1200,
    4260018: 1400,
    4260019: 1600
};

// 万分比，失败率包含15->16和16->17原表中未列出的2.1%。
var STAR_RATES = [
    {success: 9500, failure: 500, destroy: 0},
    {success: 9000, failure: 1000, destroy: 0},
    {success: 8500, failure: 1500, destroy: 0},
    {success: 8500, failure: 1500, destroy: 0},
    {success: 8000, failure: 2000, destroy: 0},
    {success: 7500, failure: 2500, destroy: 0},
    {success: 7000, failure: 3000, destroy: 0},
    {success: 6500, failure: 3500, destroy: 0},
    {success: 6000, failure: 4000, destroy: 0},
    {success: 5500, failure: 4500, destroy: 0},
    {success: 5000, failure: 5000, destroy: 0},
    {success: 4500, failure: 5500, destroy: 0},
    {success: 4000, failure: 6000, destroy: 0},
    {success: 3500, failure: 6500, destroy: 0},
    {success: 3000, failure: 7000, destroy: 0},
    {success: 3000, failure: 7000, destroy: 0},
    {success: 3000, failure: 7000, destroy: 0},
    {success: 1500, failure: 7820, destroy: 680},
    {success: 1500, failure: 7820, destroy: 680},
    {success: 1500, failure: 7650, destroy: 850},
    {success: 3000, failure: 5950, destroy: 1050},
    {success: 1500, failure: 7225, destroy: 1275},
    {success: 1500, failure: 6800, destroy: 1700},
    {success: 1000, failure: 7200, destroy: 1800},
    {success: 1000, failure: 7200, destroy: 1800}
];

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        showEnhancementMenu();
    } else if (status === 1) {
        if (selection !== 0 && selection !== 1 && selection !== 2) {
            cm.dispose();
            return;
        }
        attemptEnhancement(selection);
    } else {
        cm.dispose();
    }
}

function showEnhancementMenu() {
    var item = getSlotOneEquip();
    var error = validateEquip(item);
    if (error !== null) {
        cm.sendOk("#e#r[星之力强化]#k#n\r\n\r\n" + error +
            "\r\n\r\n请将武器放在#b装备栏第1格#k，并先用完所有卷轴升级次数。");
        cm.dispose();
        return;
    }

    var itemId = item.getItemId();
    var requiredLevel = getRequiredLevel(itemId);
    var currentStar = item.getStarLevel();
    var maxStar = getMaxStars(requiredLevel);
    var cost = getMesoCost(requiredLevel, currentStar);
    var rate = STAR_RATES[currentStar];
    var guaranteed = item.getStarCount() >= 5;
    var safeguardScroll = getSlotTwoSafeguardScroll();
    selectedScrollId = safeguardScroll === null ? 0 : safeguardScroll.itemId;

    selectedItem = {
        itemId: itemId,
        starLevel: currentStar,
        starCount: item.getStarCount(),
        upgradeSlots: item.getUpgradeSlots(),
        requiredLevel: requiredLevel,
        maxStar: maxStar
    };

    var text = "#e#b[星之力强化]#k#n\r\n\r\n";
    text += "#i" + itemId + "# #b#t" + itemId + "##k\r\n";
    text += "当前星级：#r" + currentStar + "★#k / " + maxStar + "★\r\n";
    text += "连续失败：#r" + item.getStarCount() + "#k / 5";
    if (guaranteed) text += " #e#b（本次必定成功）#k#n";
    text += "\r\n\r\n";
    text += "成功 " + formatRate(rate.success) + "% / 失败 " +
        formatRate(rate.failure) + "% / 爆装 " + formatRate(rate.destroy) + "%\r\n";
    text += "所需金币：#r" + formatMeso(cost) + "#k\r\n\r\n";
    text += "#L0##b进行强化#k#l\r\n";
    if (!guaranteed && canSafeguard(currentStar)) {
        text += "#L1##d金币保护（金币 " + formatMeso(cost * 2) +
            "，爆装转为失败）#k#l\r\n";
    }
    if (!guaranteed && rate.destroy > 0) {
        if (safeguardScroll !== null) {
            text += "#L2##d使用 #i" + safeguardScroll.itemId + "# #t" +
                safeguardScroll.itemId + "#（爆装率 " + formatRate(rate.destroy) +
                "% → " + formatRate(getAdjustedDestroyRate(
                    currentStar, safeguardScroll.reduction)) + "%）#k#l\r\n";
        } else {
            text += "\r\n#r如需使用防爆卷，请将卷轴放在其他栏第2格。#k\r\n";
        }
    }
    cm.sendSimple(text);
}

function attemptEnhancement(protectionMode) {
    var item = getSlotOneEquip();
    if (!matchesSelectedItem(item)) {
        cm.sendOk("装备栏第1格的装备状态已变化，请重新打开强化界面。");
        cm.dispose();
        return;
    }

    var error = validateEquip(item);
    if (error !== null) {
        cm.sendOk(error);
        cm.dispose();
        return;
    }
    var mesoSafeguard = protectionMode === 1;
    var useScroll = protectionMode === 2;
    if (mesoSafeguard && !canSafeguard(item.getStarLevel())) {
        cm.sendOk("防爆保护只可用于17★强化至18★。");
        cm.dispose();
        return;
    }

    var safeguardScroll = null;
    if (useScroll) {
        safeguardScroll = getSlotTwoSafeguardScroll();
        if (safeguardScroll === null || safeguardScroll.itemId !== selectedScrollId) {
            cm.sendOk("其他栏第2格的防爆卷已变化，请重新打开强化界面。");
            cm.dispose();
            return;
        }
        if (STAR_RATES[item.getStarLevel()].destroy <= 0 || item.getStarCount() >= 5) {
            cm.sendOk("本次强化没有爆装风险，无需使用防爆卷。");
            cm.dispose();
            return;
        }
    }

    var requiredLevel = getRequiredLevel(item.getItemId());
    var currentStar = item.getStarLevel();
    var maxStar = getMaxStars(requiredLevel);
    var cost = getMesoCost(requiredLevel, currentStar) * (mesoSafeguard ? 2 : 1);
    if (cm.getMeso() < cost) {
        cm.sendOk("金币不足，需要 #r" + formatMeso(cost) + "#k 金币。");
        cm.dispose();
        return;
    }

    cm.gainMeso(-cost);
    var destroyReduction = safeguardScroll === null ? 0 : safeguardScroll.reduction;
    if (safeguardScroll !== null) {
        InventoryManipulator.removeFromSlot(
            cm.getClient(), InventoryType.ETC, 2, 1, false
        );
    }
    var result = rollResult(currentStar, item.getStarCount(), destroyReduction);
    if (result === DESTROYED && mesoSafeguard) result = FAILURE;

    if (result === SUCCESS) {
        var targetStar = currentStar + 1;
        addStarStats(item, targetStar, requiredLevel);
        item.setStarLevel(targetStar);
        item.setStarCount(0);
        persistSurvivingItem(item, maxStar);
        cm.sendOk("#e#b强化成功！#k#n\r\n\r\n武器已提升至 #r" + targetStar + "★#k。");
    } else if (result === DESTROYED) {
        InventoryManipulator.removeFromSlot(
            cm.getClient(), InventoryType.EQUIP, 1, 1, false
        );
        cm.sendOk("#e#r强化失败，装备已被摧毁。#k#n");
    } else {
        var targetAfterFailure = getFailureStar(currentStar);
        if (targetAfterFailure < currentStar) {
            removeStarStats(item, currentStar, requiredLevel);
            item.setStarLevel(targetAfterFailure);
        }
        item.setStarCount(item.getStarCount() + 1);
        persistSurvivingItem(item, maxStar);
        var failureText = targetAfterFailure < currentStar
            ? "强化失败，星级下降至 #r" + targetAfterFailure + "★#k。"
            : "强化失败，星级保持 #r" + currentStar + "★#k。";
        if (item.getStarCount() >= 5) failureText += "\r\n#b下一次强化必定成功。#k";
        cm.sendOk(failureText);
    }
    cm.dispose();
}

function getSlotOneEquip() {
    return cm.getPlayer().getInventory(InventoryType.EQUIP).getItem(1);
}

function validateEquip(item) {
    if (item === null) return "装备栏第1格没有装备。";
    if (!isWeapon(item.getItemId())) return "只有武器可以进行星之力强化。";
    if (item.getUpgradeSlots() !== 0) return "必须先用完所有卷轴升级次数（可升级次数 = 0）。";
    var requiredLevel = getRequiredLevel(item.getItemId());
    if (requiredLevel < 0) return "无法读取这件武器的需求等级。";
    var maxStar = getMaxStars(requiredLevel);
    if (item.getStarLevel() < 0 || item.getStarLevel() >= maxStar) {
        return "该武器已达到最大星级，无法继续强化。";
    }
    return null;
}

function matchesSelectedItem(item) {
    return selectedItem !== null && item !== null &&
        item.getItemId() === selectedItem.itemId &&
        item.getStarLevel() === selectedItem.starLevel &&
        item.getStarCount() === selectedItem.starCount &&
        item.getUpgradeSlots() === selectedItem.upgradeSlots &&
        getRequiredLevel(item.getItemId()) === selectedItem.requiredLevel &&
        getMaxStars(selectedItem.requiredLevel) === selectedItem.maxStar;
}

function isWeapon(itemId) {
    return itemId >= 1302000 && itemId < 1493000;
}

function getRequiredLevel(itemId) {
    return ItemInformationProvider.getInstance().getEquipLevelReq(itemId);
}

function getMaxStars(requiredLevel) {
    if (requiredLevel <= 94) return 5;
    if (requiredLevel <= 107) return 8;
    if (requiredLevel <= 117) return 10;
    if (requiredLevel <= 127) return 15;
    if (requiredLevel <= 137) return 20;
    return 25;
}

function getMesoCost(requiredLevel, currentStar) {
    var levelCubed = Math.pow(requiredLevel, 3);
    var rawCost;
    if (currentStar <= 9) {
        rawCost = 1000 + levelCubed * (currentStar + 1) / 25;
    } else if (currentStar <= 14) {
        rawCost = 1000 + levelCubed * Math.pow(currentStar + 1, 2.7) / 400;
    } else {
        rawCost = 1000 + levelCubed * Math.pow(currentStar + 1, 2.7) / 200;
    }
    return Math.max(1000, Math.round(rawCost / 1000) * 1000);
}

function rollResult(currentStar, consecutiveFailures, destroyReduction) {
    if (consecutiveFailures >= 5) return SUCCESS;
    var rate = STAR_RATES[currentStar];
    var adjustedDestroy = getAdjustedDestroyRate(currentStar, destroyReduction || 0);
    var roll = Math.floor(Math.random() * 10000);
    if (roll < rate.success) return SUCCESS;
    if (roll < 10000 - adjustedDestroy) return FAILURE;
    return DESTROYED;
}

function getAdjustedDestroyRate(currentStar, reduction) {
    return Math.max(0, STAR_RATES[currentStar].destroy - reduction);
}

function canSafeguard(currentStar) {
    return currentStar === 17;
}

function getFailureStar(currentStar) {
    if (currentStar < 17 || SAFE_CHECKPOINTS[currentStar]) return currentStar;
    return currentStar - 1;
}

function getSlotTwoSafeguardScroll() {
    var item = cm.getPlayer().getInventory(InventoryType.ETC).getItem(2);
    if (item === null) return null;
    var reduction = SAFEGUARD_SCROLLS[item.getItemId()];
    if (reduction === undefined || item.getQuantity() < 1) return null;
    return {itemId: item.getItemId(), reduction: reduction};
}

function addStarStats(item, targetStar, requiredLevel) {
    var gain = targetStar <= 15
        ? {main: targetStar <= 5 ? 2 : 3, attack: null}
        : getFixedStarGain(requiredLevel, targetStar);
    addMainStat(item, gain.main);
    if (item.getWatk() > 0) {
        item.setWatk(item.getWatk() + (gain.attack === null
            ? Math.floor(item.getWatk() / 50) + 1 : gain.attack));
    }
    if (item.getMatk() > 0) {
        item.setMatk(item.getMatk() + (gain.attack === null
            ? Math.floor(item.getMatk() / 50) + 1 : gain.attack));
    }
}

function removeStarStats(item, removedStar, requiredLevel) {
    var gain = getFixedStarGain(requiredLevel, removedStar);
    addMainStat(item, -gain.main);
    if (item.getWatk() > 0) item.setWatk(Math.max(0, item.getWatk() - gain.attack));
    if (item.getMatk() > 0) item.setMatk(Math.max(0, item.getMatk() - gain.attack));
}

function getFixedStarGain(requiredLevel, targetStar) {
    if (requiredLevel <= 137) return {main: 7, attack: targetStar - 9};
    if (requiredLevel <= 147) return {main: 9, attack: targetStar - 8};
    if (requiredLevel <= 157) return {main: 11, attack: targetStar - 7};
    if (requiredLevel <= 199) return {main: 13, attack: targetStar - 6};
    return {main: 15, attack: targetStar - 4};
}

function addMainStat(item, amount) {
    var category = Math.floor(item.getItemId() / 10000);
    if ([130, 131, 132, 140, 141, 142, 143, 144, 148].indexOf(category) >= 0) {
        item.setStr(Math.max(0, item.getStr() + amount));
    } else if ([133, 134, 136, 147].indexOf(category) >= 0) {
        item.setLuk(Math.max(0, item.getLuk() + amount));
    } else if ([137, 138].indexOf(category) >= 0) {
        item.setInt(Math.max(0, item.getInt() + amount));
    } else if ([145, 146, 149].indexOf(category) >= 0) {
        item.setDex(Math.max(0, item.getDex() + amount));
    }
}

function persistSurvivingItem(item, maxStar) {
    item.setMaxStar(maxStar);
    item.setOwner(item.getStarLevel() + "★");
    cm.getPlayer().forceUpdateItem(item);
}

function formatRate(basisPoints) {
    return basisPoints % 100 === 0
        ? String(basisPoints / 100)
        : String(basisPoints / 100).replace(/0+$/, "");
}

function formatMeso(value) {
    return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}
