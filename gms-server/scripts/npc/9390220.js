var status = -1;
var stage = "main";
var selectedRoute = -1;
var selectedGood = -1;

var AREA_ID = 32010;
var DENARO = 4310100;
var LOBBY_MAP = 865000001;
var MIN_LEVEL = 140;
var DAILY_STOCK = [6, 5, 4, 3, 1, 1];
var routeNames = ["多尔切", "露娜", "罗萨", "赫尔", "里恩", "北方海域"];
var routeEnergy = [10, 12, 15, 20, 25, 30];
var routeExperience = [180, 300, 420, 1000, 1500, 2200];
var routeMinutes = [3, 5, 7, 9, 11, 13];
var routeUnlockCost = [0, 5, 10, 20, 30, 50];
var routeBaseReward = [1, 2, 3, 4, 5, 6];
var shipNames = ["货船", "帆船", "无型舰"];
var tierCargoLimit = [2, 4, 6];
var tierEnergyLimit = [100, 110, 120];
var goods = [
    { name: "肥皂", currency: "meso", cost: 100000, profit: [2, 3, 4, 5, 6, 7] },
    { name: "皮革", currency: "meso", cost: 250000, profit: [1, 4, 6, 7, 8, 10] },
    { name: "香草", currency: "meso", cost: 400000, profit: [1, 2, 7, 10, 11, 13] },
    { name: "海鲜", currency: "meso", cost: 600000, profit: [2, 2, 4, 9, 12, 15] },
    { name: "藏宝图", currency: "denaro", cost: 30, profit: [10, 12, 16, 20, 28, 40] },
    { name: "五色鳞片", currency: "denaro", cost: 50, profit: [14, 18, 22, 28, 40, 65] }
];
var Short = Java.type("java.lang.Short");
var SimpleDateFormat = Java.type("java.text.SimpleDateFormat");
var Date = Java.type("java.util.Date");

function start() {
    status = -1;
    action(1, 0, 0);
}

function intValue(value, fallback) {
    var parsed = parseInt(value);
    return isNaN(parsed) ? fallback : parsed;
}

function intArray(value, length, defaults) {
    var source = value == null ? [] : String(value).split(",");
    var result = [];
    for (var i = 0; i < length; i++) result.push(intValue(source[i], defaults[i]));
    return result;
}

function todayKey() {
    return String(new SimpleDateFormat("yyyyMMdd").format(new Date()));
}

function defaultState() {
    return {
        day: todayKey(), tier: 0, level: 1, exp: 0,
        energy: 100, energyCap: 100, cargoCap: 2, unlockMask: 1,
        counts: [0, 0, 0, 0, 0, 0], stock: DAILY_STOCK.slice(0),
        cargo: [0, 0, 0, 0, 0, 0], pendingCoins: 0, pendingExp: 0,
        pendingItem: 0, pendingItemQty: 0, active: 0, activeRoute: -1,
        activeReward: 0, activeExp: 0, activeCargo: 0
    };
}

function stateKey() {
    return Short.valueOf(String(AREA_ID));
}

function encodeState(s) {
    return [
        "C1", s.day, s.tier, s.level, s.exp, s.energy, s.energyCap,
        s.cargoCap, s.unlockMask, s.counts.join(","), s.stock.join(","),
        s.cargo.join(","), s.pendingCoins, s.pendingExp, s.pendingItem,
        s.pendingItemQty, s.active, s.activeRoute, s.activeReward,
        s.activeExp, s.activeCargo
    ].join("|");
}

function decodeState(raw) {
    if (raw == null) return defaultState();
    var p = String(raw).split("|");
    if (p.length < 21 || p[0] != "C1") return defaultState();
    var s = defaultState();
    s.day = p[1];
    s.tier = Math.max(0, Math.min(2, intValue(p[2], 0)));
    s.level = Math.max(1, Math.min(10, intValue(p[3], 1)));
    s.exp = Math.max(0, intValue(p[4], 0));
    s.energyCap = Math.max(100, Math.min(tierEnergyLimit[s.tier], intValue(p[6], 100)));
    s.energy = Math.max(0, Math.min(s.energyCap, intValue(p[5], s.energyCap)));
    s.cargoCap = Math.max(2, Math.min(tierCargoLimit[s.tier], intValue(p[7], 2)));
    s.unlockMask = intValue(p[8], 1) | 1;
    s.counts = intArray(p[9], 6, [0, 0, 0, 0, 0, 0]);
    s.stock = intArray(p[10], 6, DAILY_STOCK);
    s.cargo = intArray(p[11], 6, [0, 0, 0, 0, 0, 0]);
    s.pendingCoins = Math.max(0, intValue(p[12], 0));
    s.pendingExp = Math.max(0, intValue(p[13], 0));
    s.pendingItem = Math.max(0, intValue(p[14], 0));
    s.pendingItemQty = Math.max(0, intValue(p[15], 0));
    s.active = intValue(p[16], 0) == 1 ? 1 : 0;
    s.activeRoute = intValue(p[17], -1);
    s.activeReward = Math.max(0, intValue(p[18], 0));
    s.activeExp = Math.max(0, intValue(p[19], 0));
    s.activeCargo = Math.max(0, intValue(p[20], 0));
    return s;
}

function saveState(player, s) {
    player.getAreaInfos().put(stateKey(), encodeState(s));
}

function loadState(player) {
    var s = decodeState(player.getAreaInfos().get(stateKey()));
    var changed = false;
    if (s.day != todayKey()) {
        s.day = todayKey();
        s.energy = s.energyCap;
        s.stock = DAILY_STOCK.slice(0);
        changed = true;
    }
    if (s.active == 1 && player.getMapId() == LOBBY_MAP) {
        s.active = 0;
        s.activeRoute = -1;
        s.activeReward = 0;
        s.activeExp = 0;
        s.activeCargo = 0;
        changed = true;
    }
    if (changed) saveState(player, s);
    return s;
}

function cargoUsed(s) {
    var total = 0;
    for (var i = 0; i < s.cargo.length; i++) total += s.cargo[i];
    return total;
}

function cargoReward(s, route) {
    var reward = routeBaseReward[route];
    for (var i = 0; i < goods.length; i++) reward += s.cargo[i] * goods[i].profit[route];
    return reward;
}

function currencyText(good) {
    return good.currency == "meso"
        ? good.cost.toLocaleString() + " 金币"
        : good.cost + " 枚凯梅尔兹金币";
}

function showMain() {
    var s = loadState(cm.getPlayer());
    stage = "main";
    var text = "#e凯梅尔兹贸易#n\r\n";
    text += "舰船：#b" + shipNames[s.tier] + " Lv." + s.level + "#k  ";
    text += "能量：#r" + s.energy + "/" + s.energyCap + "#k\r\n";
    text += "船舱：#b" + cargoUsed(s) + "/" + s.cargoCap + "#k  ";
    text += "凯梅尔兹金币：#b" + cm.itemQuantity(DENARO) + "#k\r\n\r\n";
    text += "#L0##b进行贸易#k#l\r\n";
    text += "#L1#查看舰船状态#l\r\n";
    text += "#L2#购买并装载贸易品#l\r\n";
    text += "#L3#查看或清空船舱#l\r\n";
    text += "#L4#升级船舱空间#l\r\n";
    text += "#L5#提高能量上限#l\r\n";
    text += "#L6#升级船只#l";
    cm.sendSimple(text);
}

function showStatus() {
    var s = loadState(cm.getPlayer());
    var text = "#e舰船状态#n\r\n";
    text += "船型：#b" + shipNames[s.tier] + "#k\r\n";
    text += "等级：#b" + s.level + "/10#k\r\n";
    text += "经验：#b" + (s.level == 10 ? "已满级" : s.exp + "/10000") + "#k\r\n";
    text += "当前能量：#r" + s.energy + "/" + s.energyCap + "#k（每日 00:00 恢复）\r\n";
    text += "船舱：#b" + cargoUsed(s) + "/" + s.cargoCap + "#k\r\n\r\n";
    text += "#e航线进度#n\r\n";
    for (var i = 0; i < routeNames.length; i++) {
        var unlocked = (s.unlockMask & (1 << i)) != 0;
        text += routeNames[i] + "：" + (unlocked ? "#b已解锁#k" : "#r未解锁#k");
        text += "，完成 " + s.counts[i] + " 次\r\n";
    }
    if (s.pendingCoins > 0 || s.pendingExp > 0 || s.pendingItem > 0) {
        text += "\r\n#r有航海收益尚未向仔北卢领取。#k";
    }
    cm.sendOk(text);
    cm.dispose();
}

function showRoutes() {
    var s = loadState(cm.getPlayer());
    stage = "route";
    var text = "#e选择目的地#n\r\n已装载 " + cargoUsed(s) + "/" + s.cargoCap + " 格货物。\r\n";
    for (var i = 0; i < routeNames.length; i++) {
        var unlocked = (s.unlockMask & (1 << i)) != 0;
        text += "#L" + i + "#" + (unlocked ? "#b" : "#r[未解锁] ");
        text += routeNames[i] + "#k - " + routeEnergy[i] + " 能量，约 " + routeMinutes[i];
        text += " 分钟，舰船经验 " + routeExperience[i] + "#l\r\n";
    }
    cm.sendSimple(text);
}

function showGoods() {
    var s = loadState(cm.getPlayer());
    stage = "good";
    var free = s.cargoCap - cargoUsed(s);
    var text = "#e购买并装载贸易品#n\r\n船舱剩余：#b" + free + " 格#k\r\n";
    text += "每日供应会在 00:00 刷新，已装船货物不会被清除。\r\n\r\n";
    for (var i = 0; i < goods.length; i++) {
        text += "#L" + i + "##b" + goods[i].name + "#k#l - " + currencyText(goods[i]);
        text += "，今日剩余 #r" + s.stock[i] + "#k\r\n";
    }
    cm.sendSimple(text);
}

function showCargo() {
    var s = loadState(cm.getPlayer());
    var used = cargoUsed(s);
    var text = "#e当前船舱#n  " + used + "/" + s.cargoCap + "\r\n";
    if (used == 0) {
        cm.sendOk(text + "尚未装载贸易品。");
        cm.dispose();
        return;
    }
    for (var i = 0; i < goods.length; i++) {
        if (s.cargo[i] > 0) text += goods[i].name + " x " + s.cargo[i] + "\r\n";
    }
    text += "\r\n#e预计到港收益（含航线基础奖励）#n\r\n";
    for (var r = 0; r < routeNames.length; r++) {
        text += routeNames[r] + "：#b" + cargoReward(s, r) + "#k 枚凯梅尔兹金币\r\n";
    }
    text += "\r\n#L99##r清空船舱（不返还购买费用）#k#l";
    stage = "cargo";
    cm.sendSimple(text);
}

function askCargoUpgrade() {
    var s = loadState(cm.getPlayer());
    var limit = tierCargoLimit[s.tier];
    if (s.cargoCap >= limit) {
        cm.sendOk(s.tier == 2 ? "当前船舱已经达到最高的 6 格。" : "当前船型最多拥有 " + limit + " 格船舱，请先将船只升阶。");
        cm.dispose();
        return;
    }
    var cost = 20 + (s.cargoCap - 2) * 10;
    stage = "cargoUpgrade";
    cm.sendYesNo("将船舱从 #b" + s.cargoCap + " 格#k扩充到 #b" + (s.cargoCap + 1) + " 格#k，需要 #r" + cost + " 枚凯梅尔兹金币#k。是否扩充？");
}

function askEnergyUpgrade() {
    var s = loadState(cm.getPlayer());
    var limit = tierEnergyLimit[s.tier];
    if (s.energyCap >= limit) {
        cm.sendOk(s.tier == 2 ? "舰船能量上限已经达到最高的 120 点。" : "当前船型的能量上限是 " + limit + " 点，请先将船只升阶。");
        cm.dispose();
        return;
    }
    var cost = 20 + ((s.energyCap - 100) / 5) * 10;
    stage = "energyUpgrade";
    cm.sendYesNo("将能量上限从 #b" + s.energyCap + "#k提高到 #b" + (s.energyCap + 5) + "#k，需要 #r" + cost + " 枚凯梅尔兹金币#k。是否升级？");
}

function askShipUpgrade() {
    var s = loadState(cm.getPlayer());
    if (s.tier >= 2) {
        cm.sendOk("你已经拥有最高级的无型舰。");
        cm.dispose();
        return;
    }
    if (s.level < 10) {
        cm.sendOk("船只达到 10 级后才能升阶。当前为 " + shipNames[s.tier] + " Lv." + s.level + "。");
        cm.dispose();
        return;
    }
    var cost = s.tier == 0 ? 10000000 : 30000000;
    stage = "shipUpgrade";
    cm.sendYesNo("将 #b" + shipNames[s.tier] + "#k升级为 #b" + shipNames[s.tier + 1] + "#k，需要 #r" + cost.toLocaleString() + " 金币#k。升级后船只等级重置为 1，并开放更高的船舱与能量上限。是否升级？");
}

function unlockRoute(route) {
    var s = loadState(cm.getPlayer());
    var previous = route - 1;
    if (route <= 0 || (s.unlockMask & (1 << route)) != 0) {
        cm.sendOk("该航线已经解锁。");
        cm.dispose();
        return;
    }
    if ((s.unlockMask & (1 << previous)) == 0 || s.counts[previous] < 5) {
        cm.sendOk("需要先解锁并完成 #b" + routeNames[previous] + "#k 5 次。当前完成 " + s.counts[previous] + " 次。");
        cm.dispose();
        return;
    }
    var cost = routeUnlockCost[route];
    if (!cm.haveItem(DENARO, cost)) {
        cm.sendOk("解锁需要 #r" + cost + " 枚凯梅尔兹金币#k。你目前只有 " + cm.itemQuantity(DENARO) + " 枚。");
        cm.dispose();
        return;
    }
    cm.gainItem(DENARO, -cost);
    s.unlockMask |= (1 << route);
    saveState(cm.getPlayer(), s);
    cm.sendOk("已解锁 #b" + routeNames[route] + "#k 航线。");
    cm.dispose();
}

function getVoyageMembers() {
    var party = cm.getParty();
    if (party == null || party.getPartyMembersOnline().size() <= 1) return [cm.getPlayer()];
    if (!cm.isLeader()) return "请让队长来选择航线并发起航海。";
    var result = [];
    var online = party.getPartyMembersOnline();
    for (var i = 0; i < online.size(); i++) {
        var member = online.get(i).getPlayer();
        if (member == null || member.getMapId() != LOBBY_MAP || member.getLevel() < MIN_LEVEL) {
            return "多人航海时，所有在线队员都需要达到 140 级，并与队长一起位于交易所。";
        }
        result.push(member);
    }
    return result;
}

function validateVoyageMember(player, route) {
    var s = loadState(player);
    if ((s.unlockMask & (1 << route)) == 0) return player.getName() + " 尚未解锁 " + routeNames[route] + "。";
    if (s.energy < routeEnergy[route]) return player.getName() + " 的舰船能量不足。";
    if (cargoUsed(s) <= 0) return player.getName() + " 尚未装载贸易品。";
    if (s.pendingCoins > 0 || s.pendingExp > 0 || s.pendingItem > 0) return player.getName() + " 尚有航海收益未领取。";
    if (s.active != 0) return player.getName() + " 已经处于航海状态。";
    return null;
}

function launchVoyage(route) {
    var members = getVoyageMembers();
    if (typeof members == "string") {
        cm.sendOk(members);
        cm.dispose();
        return;
    }
    var backups = [];
    for (var i = 0; i < members.length; i++) {
        var problem = validateVoyageMember(members[i], route);
        if (problem != null) {
            cm.sendOk(problem);
            cm.dispose();
            return;
        }
    }
    for (var j = 0; j < members.length; j++) {
        var player = members[j];
        var s = loadState(player);
        backups.push(encodeState(s));
        s.energy -= routeEnergy[route];
        s.active = 1;
        s.activeRoute = route;
        s.activeReward = cargoReward(s, route);
        s.activeExp = routeExperience[route];
        s.activeCargo = cargoUsed(s);
        s.cargo = [0, 0, 0, 0, 0, 0];
        saveState(player, s);
    }

    var em = cm.getEventManager("CommerciVoyage");
    var started = false;
    if (em != null) {
        var party = cm.getParty();
        if (party == null || members.length == 1) started = em.startInstance(-1, cm.getPlayer(), cm.getPlayer(), route + 1);
        else started = em.startInstance(party, cm.getPlayer().getMap(), route + 1);
    }
    if (!started) {
        for (var k = 0; k < members.length; k++) members[k].getAreaInfos().put(stateKey(), backups[k]);
        cm.sendOk("当前航海大厅正在释放，请稍后再试。能源和货物没有被扣除。");
    }
    cm.dispose();
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    if (status == -1) {
        status = 0;
        showMain();
        return;
    }

    if (stage == "main") {
        if (selection == 0) showRoutes();
        else if (selection == 1) showStatus();
        else if (selection == 2) showGoods();
        else if (selection == 3) showCargo();
        else if (selection == 4) askCargoUpgrade();
        else if (selection == 5) askEnergyUpgrade();
        else if (selection == 6) askShipUpgrade();
        return;
    }

    if (stage == "route") {
        selectedRoute = intValue(selection, -1);
        if (selectedRoute < 0 || selectedRoute >= routeNames.length) {
            cm.dispose();
            return;
        }
        var routeState = loadState(cm.getPlayer());
        if ((routeState.unlockMask & (1 << selectedRoute)) == 0) {
            var previous = selectedRoute - 1;
            if (routeState.counts[previous] < 5) {
                cm.sendOk("解锁 #b" + routeNames[selectedRoute] + "#k 需要先完成 #b" + routeNames[previous] + "#k 5 次。当前完成 " + routeState.counts[previous] + " 次。");
                cm.dispose();
                return;
            }
            stage = "unlockRoute";
            cm.sendYesNo("解锁 #b" + routeNames[selectedRoute] + "#k 需要一次性支付 #r" + routeUnlockCost[selectedRoute] + " 枚凯梅尔兹金币#k。是否解锁？");
            return;
        }
        if (cargoUsed(routeState) <= 0) {
            cm.sendOk("出航前必须先购买并装载至少 1 格贸易品。");
            cm.dispose();
            return;
        }
        stage = "launch";
        cm.sendYesNo("目的地：#b" + routeNames[selectedRoute] + "#k\r\n消耗能量：#r" + routeEnergy[selectedRoute] + "#k\r\n预计基础时间：" + routeMinutes[selectedRoute] + " 分钟\r\n预计收益：#b" + cargoReward(routeState, selectedRoute) + " 枚凯梅尔兹金币#k\r\n\r\n怪物会在途中分波出现。消灭怪物会缩短航行时间；即使不清怪也能到港，但未清波次可能造成货损。确认出航吗？");
        return;
    }
    if (stage == "unlockRoute") {
        unlockRoute(selectedRoute);
        return;
    }
    if (stage == "launch") {
        launchVoyage(selectedRoute);
        return;
    }
    if (stage == "good") {
        selectedGood = intValue(selection, -1);
        var buyState = loadState(cm.getPlayer());
        if (selectedGood < 0 || selectedGood >= goods.length || buyState.stock[selectedGood] <= 0) {
            cm.sendOk("该贸易品今日已经售罄。");
            cm.dispose();
            return;
        }
        var maxBuy = Math.min(buyState.stock[selectedGood], buyState.cargoCap - cargoUsed(buyState));
        if (maxBuy <= 0) {
            cm.sendOk("船舱已满。");
            cm.dispose();
            return;
        }
        stage = "goodQuantity";
        cm.sendGetNumber("要购买并装载多少份 #b" + goods[selectedGood].name + "#k？\r\n单价：" + currencyText(goods[selectedGood]) + "\r\n最多可装载 " + maxBuy + " 份。", 1, 1, maxBuy);
        return;
    }
    if (stage == "goodQuantity") {
        var quantity = intValue(selection, 0);
        var s = loadState(cm.getPlayer());
        var max = Math.min(s.stock[selectedGood], s.cargoCap - cargoUsed(s));
        if (quantity <= 0 || quantity > max) {
            cm.sendOk("购买数量无效。");
            cm.dispose();
            return;
        }
        var good = goods[selectedGood];
        var totalCost = good.cost * quantity;
        if (good.currency == "meso") {
            if (cm.getMeso() < totalCost) {
                cm.sendOk("金币不足，需要 " + totalCost.toLocaleString() + " 金币。");
                cm.dispose();
                return;
            }
            cm.gainMeso(-totalCost);
        } else {
            if (!cm.haveItem(DENARO, totalCost)) {
                cm.sendOk("凯梅尔兹金币不足，需要 " + totalCost + " 枚。");
                cm.dispose();
                return;
            }
            cm.gainItem(DENARO, -totalCost);
        }
        s.stock[selectedGood] -= quantity;
        s.cargo[selectedGood] += quantity;
        saveState(cm.getPlayer(), s);
        cm.sendOk("已购买并装载 #b" + good.name + " x " + quantity + "#k。当前船舱 " + cargoUsed(s) + "/" + s.cargoCap + "。");
        cm.dispose();
        return;
    }
    if (stage == "cargo") {
        if (selection == 99) {
            var clearState = loadState(cm.getPlayer());
            clearState.cargo = [0, 0, 0, 0, 0, 0];
            saveState(cm.getPlayer(), clearState);
            cm.sendOk("船舱已经清空，购买费用不予返还。");
        }
        cm.dispose();
        return;
    }
    if (stage == "cargoUpgrade") {
        var cargoState = loadState(cm.getPlayer());
        var cargoCost = 20 + (cargoState.cargoCap - 2) * 10;
        if (cargoState.cargoCap >= tierCargoLimit[cargoState.tier] || !cm.haveItem(DENARO, cargoCost)) cm.sendOk("无法扩充船舱，请确认船型和凯梅尔兹金币数量。");
        else {
            cm.gainItem(DENARO, -cargoCost);
            cargoState.cargoCap++;
            saveState(cm.getPlayer(), cargoState);
            cm.sendOk("船舱已扩充为 #b" + cargoState.cargoCap + " 格#k。");
        }
        cm.dispose();
        return;
    }
    if (stage == "energyUpgrade") {
        var energyState = loadState(cm.getPlayer());
        var energyCost = 20 + ((energyState.energyCap - 100) / 5) * 10;
        if (energyState.energyCap >= tierEnergyLimit[energyState.tier] || !cm.haveItem(DENARO, energyCost)) cm.sendOk("无法提高能量上限，请确认船型和凯梅尔兹金币数量。");
        else {
            cm.gainItem(DENARO, -energyCost);
            energyState.energyCap += 5;
            energyState.energy = Math.min(energyState.energyCap, energyState.energy + 5);
            saveState(cm.getPlayer(), energyState);
            cm.sendOk("能量上限已提高到 #b" + energyState.energyCap + "#k，当前能量为 " + energyState.energy + "。");
        }
        cm.dispose();
        return;
    }
    if (stage == "shipUpgrade") {
        var shipState = loadState(cm.getPlayer());
        var shipCost = shipState.tier == 0 ? 10000000 : 30000000;
        if (shipState.tier >= 2 || shipState.level < 10 || cm.getMeso() < shipCost) cm.sendOk("无法升级船只，请确认等级和金币数量。");
        else {
            cm.gainMeso(-shipCost);
            shipState.tier++;
            shipState.level = 1;
            shipState.exp = 0;
            saveState(cm.getPlayer(), shipState);
            cm.sendOk("船只已升级为 #b" + shipNames[shipState.tier] + "#k。现在可以继续扩充船舱和能量上限。");
        }
        cm.dispose();
        return;
    }
    cm.dispose();
}
