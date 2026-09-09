/**
 * 9209005 — 锻造系统 (680100000)
 * 不速之客 / 乌特格鲁德可合成；法弗纳、漩涡占位。
 */

var status = -1;
var series = -1;
var guestTier = -1;
var item;
var mats;
var matQty;
var mesoCost;
var nxCost;

var GUEST = [
    [
        [1372074, 43], [1302143, 47], [1312058, 47], [1322086, 47], [1332116, 47],
        [1402086, 47], [1412058, 47], [1422059, 47], [1432077, 47], [1452102, 47],
        [1462087, 47], [1472113, 47], [1482075, 47], [1492075, 47], [1382095, 49]
    ],
    [
        [1372075, 66], [1302144, 67], [1312059, 67], [1322087, 67], [1332117, 67],
        [1402087, 67], [1412059, 67], [1422060, 67], [1432078, 67], [1452103, 67],
        [1462088, 67], [1472114, 67], [1482076, 67], [1492076, 67], [1382096, 69]
    ],
    [
        [1372076, 86], [1302145, 87], [1312060, 87], [1322088, 87], [1332118, 87],
        [1402088, 87], [1412060, 87], [1422061, 87], [1432079, 87], [1452104, 87],
        [1462089, 87], [1472115, 87], [1482077, 87], [1492077, 87], [1382097, 89]
    ],
    [
        [1372077, 105], [1302146, 107], [1312061, 107], [1322089, 107], [1332119, 107],
        [1382098, 107], [1402089, 107], [1412061, 107], [1422062, 107], [1432080, 107],
        [1452105, 107], [1462090, 107], [1472116, 107], [1482078, 107], [1492078, 107]
    ],
    [
        [1372078, 125], [1302147, 127], [1312062, 127], [1322090, 127], [1332120, 127],
        [1382099, 127], [1402090, 127], [1412062, 127], [1422063, 127], [1432081, 127],
        [1452106, 127], [1462091, 127], [1472117, 127], [1482079, 127], [1492079, 127]
    ]
];

var UTGARD = [
    [1302315, 140], [1312185, 140], [1322236, 140], [1332260, 140],
    [1372207, 140], [1382245, 140], [1402236, 140], [1412164, 140],
    [1422171, 140], [1432200, 140], [1442254, 140], [1452238, 140],
    [1462225, 140], [1472247, 140], [1482202, 140], [1492212, 140]
];

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        var text = "欢迎来到锻造系统，我什么都能造！客官请选择你要锻造的装备#b";
        var options = ["不速之客系列", "乌特格鲁德系列", "法弗纳系列", "漩涡系列"];
        for (var i = 0; i < options.length; i++) {
            text += "\r\n#L" + i + "# " + options[i] + "#l";
        }
        cm.sendSimple(text);
    } else if (status == 1) {
        series = selection;
        if (series == 0) {
            var sel = "不速之客系列请选择阶段：#b";
            var tiers = ["第一系列", "第二系列", "第三系列", "最终系列", "至尊系列"];
            for (var t = 0; t < tiers.length; t++) {
                sel += "\r\n#L" + t + "# " + tiers[t] + "#l";
            }
            cm.sendSimple(sel);
        } else if (series == 1) {
            sendWeaponList(UTGARD);
        } else if (series == 2) {
            cm.sendOk("法弗纳系列还在筹备中，请稍后再来。");
            cm.dispose();
        } else {
            cm.sendOk("漩涡系列还在筹备中，请稍后再来。");
            cm.dispose();
        }
    } else if (status == 2) {
        if (series == 0) {
            guestTier = selection;
            sendWeaponList(GUEST[guestTier]);
        } else {
            setUtgardRecipe(selection);
            sendConfirm();
        }
    } else if (status == 3) {
        if (series == 0) {
            setGuestRecipe(selection);
            sendConfirm();
        } else {
            doCraft();
        }
    } else if (status == 4) {
        doCraft();
    } else {
        cm.dispose();
    }
}

function sendWeaponList(list) {
    var sel = "请选择要锻造的装备：#b";
    for (var i = 0; i < list.length; i++) {
        sel += "\r\n#L" + i + "# #i" + list[i][0] + "# #t" + list[i][0] + "# (Lv." + list[i][1] + ")#l";
    }
    cm.sendSimple(sel);
}

function sendConfirm() {
    var prompt = "你想锻造 #i" + item + "##b#z" + item + "##k 吗？请确认材料充足，并保证背包有空位。#b";
    for (var i = 0; i < mats.length; i++) {
        prompt += "\r\n#i" + mats[i] + "# " + matQty[i] + "个  #t" + mats[i] + "#";
    }
    if (nxCost > 0) {
        prompt += "\r\n点券 " + nxCost;
    }
    if (mesoCost > 0) {
        prompt += "\r\n#i4031138# " + mesoCost + " 金币";
    }
    cm.sendYesNo(prompt);
}

function addMat(list, qtyList, id, qty) {
    list.push(id);
    qtyList.push(qty);
}

function findByType(list, itemId) {
    var cat = Math.floor(itemId / 10000);
    for (var i = 0; i < list.length; i++) {
        if (Math.floor(list[i][0] / 10000) == cat) {
            return list[i][0];
        }
    }
    return 0;
}

function setGuestRecipe(selection) {
    var row = GUEST[guestTier][selection];
    item = row[0];
    mats = [];
    matQty = [];
    if (guestTier == 0) {
        addMat(mats, matQty, 4000117, 500);
        addMat(mats, matQty, 4000118, 500);
        addMat(mats, matQty, 4000119, 500);
        addMat(mats, matQty, 4000120, 500);
        addMat(mats, matQty, 4000121, 500);
        addMat(mats, matQty, 4000122, 500);
        addMat(mats, matQty, 4000695, 1);
        mesoCost = 5000000;
        nxCost = 1000;
    } else if (guestTier == 1) {
        addMat(mats, matQty, 4000695, 1);
        addMat(mats, matQty, 4000125, 50);
        addMat(mats, matQty, 4000126, 50);
        addMat(mats, matQty, 4000111, 500);
        addMat(mats, matQty, 4000112, 500);
        addMat(mats, matQty, 4000115, 500);
        addMat(mats, matQty, 2388031, 5);
        addMat(mats, matQty, 4011006, 10);
        mesoCost = 8000000;
        nxCost = 2000;
    } else if (guestTier == 2) {
        addMat(mats, matQty, findByType(GUEST[0], item), 1);
        addMat(mats, matQty, findByType(GUEST[1], item), 1);
        addMat(mats, matQty, 4021000, 20);
        addMat(mats, matQty, 4021001, 20);
        addMat(mats, matQty, 4021002, 20);
        addMat(mats, matQty, 4021003, 20);
        addMat(mats, matQty, 4021004, 20);
        addMat(mats, matQty, 4021005, 20);
        addMat(mats, matQty, 4021006, 20);
        addMat(mats, matQty, 4021007, 20);
        addMat(mats, matQty, 4011007, 20);
        addMat(mats, matQty, 4021009, 20);
        mesoCost = 50000000;
        nxCost = 5000;
    } else if (guestTier == 3) {
        addMat(mats, matQty, findByType(GUEST[2], item), 1);
        addMat(mats, matQty, 4000147, 500);
        addMat(mats, matQty, 4000148, 500);
        addMat(mats, matQty, 4000132, 500);
        addMat(mats, matQty, 4000133, 500);
        addMat(mats, matQty, 4000240, 300);
        addMat(mats, matQty, 2385021, 5);
        addMat(mats, matQty, 4005000, 10);
        addMat(mats, matQty, 4005001, 10);
        addMat(mats, matQty, 4005002, 10);
        addMat(mats, matQty, 4005003, 10);
        addMat(mats, matQty, 4005004, 10);
        mesoCost = 200000000;
        nxCost = 8000;
    } else {
        addMat(mats, matQty, findByType(GUEST[3], item), 1);
        addMat(mats, matQty, 4031817, 50);
        addMat(mats, matQty, 4031818, 50);
        addMat(mats, matQty, 4031819, 50);
        addMat(mats, matQty, 4031820, 50);
        addMat(mats, matQty, 4032028, 500);
        addMat(mats, matQty, 4000696, 50);
        addMat(mats, matQty, 4032056, 50);
        addMat(mats, matQty, 4000244, 50);
        addMat(mats, matQty, 4000245, 50);
        addMat(mats, matQty, 4000175, 10);
        addMat(mats, matQty, 1672008, 1);
        mesoCost = 500000000;
        nxCost = 15000;
    }
}

function setUtgardRecipe(selection) {
    item = UTGARD[selection][0];
    mats = [];
    matQty = [];
    addMat(mats, matQty, 4000151, 50);
    addMat(mats, matQty, 4000152, 50);
    addMat(mats, matQty, 4011007, 10);
    addMat(mats, matQty, 4021009, 10);
    addMat(mats, matQty, 4003002, 100);
    addMat(mats, matQty, 4003000, 50);
    addMat(mats, matQty, 4003001, 50);
    addMat(mats, matQty, 4031875, 50);
    addMat(mats, matQty, 4251200, 1);
    addMat(mats, matQty, 4032056, 1);
    addMat(mats, matQty, 4031821, 1);
    addMat(mats, matQty, 4001141, 1);
    addMat(mats, matQty, getManualID(item), 1);
    addMat(mats, matQty, getStimID(item), 1);
    mesoCost = 0;
    nxCost = 0;
}

function doCraft() {
    if (!cm.canHold(item, 1)) {
        cm.sendOk("请先确认背包有空位。");
        cm.dispose();
        return;
    }
    if (cm.getMeso() < mesoCost) {
        cm.sendOk("金币不足，凑齐后再来。");
        cm.dispose();
        return;
    }
    if (nxCost > 0 && cm.getPlayer().getCashShop().getCash(1) < nxCost) {
        cm.sendOk("点券不足，凑齐后再来。");
        cm.dispose();
        return;
    }
    var complete = true;
    for (var i = 0; complete && i < mats.length; i++) {
        if (!cm.haveItem(mats[i], matQty[i])) {
            complete = false;
        }
    }
    if (!complete) {
        cm.sendOk("材料不足，请按清单把东西带齐。");
        cm.dispose();
        return;
    }
    for (var j = 0; j < mats.length; j++) {
        cm.gainItem(mats[j], -matQty[j]);
    }
    if (mesoCost > 0) {
        cm.gainMeso(-mesoCost);
    }
    if (nxCost > 0) {
        cm.getPlayer().getCashShop().gainCash(1, -nxCost);
    }
    cm.gainItem(item, 1);
    cm.sendOk("锻造完成了，好好使用这件装备。");
    cm.dispose();
}

function getStimID(equipID) {
    var cat = Math.floor(equipID / 10000);
    switch (cat) {
        case 130:
            return 4130002;
        case 131:
            return 4130003;
        case 132:
            return 4130004;
        case 140:
            return 4130005;
        case 141:
            return 4130006;
        case 142:
            return 4130007;
        case 143:
            return 4130008;
        case 144:
            return 4130009;
        case 137:
            return 4130010;
        case 138:
            return 4130011;
        case 145:
            return 4130012;
        case 146:
            return 4130013;
        case 133:
            return 4130014;
        case 147:
            return 4130015;
        case 148:
            return 4130016;
        case 149:
            return 4130017;
    }
    return 4130002;
}

function getManualID(equipID) {
    var cat = Math.floor(equipID / 10000);
    switch (cat) {
        case 130:
            return 4131000;
        case 131:
            return 4131001;
        case 132:
            return 4131002;
        case 140:
            return 4131003;
        case 141:
            return 4131004;
        case 142:
            return 4131005;
        case 143:
            return 4131006;
        case 144:
            return 4131007;
        case 137:
            return 4131008;
        case 138:
            return 4131009;
        case 145:
            return 4131010;
        case 146:
            return 4131011;
        case 133:
            return 4131012;
        case 147:
            return 4131013;
        case 148:
            return 4131014;
        case 149:
            return 4131015;
    }
    return 4131000;
}
