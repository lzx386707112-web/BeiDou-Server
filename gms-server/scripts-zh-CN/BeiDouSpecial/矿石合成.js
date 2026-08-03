/* Author: aaroncsn <MapleSea Like>
	NPC Name: 		Muhammad
	Map(s): 		Ariant:The Town of Ariant(260000200)
	Description: 	Jewel Refiner
*/

var status = 0;
var selectedType = -1;
var selectedItem = -1;
var item;
var mats;
var matQty;
var cost;
var qty;
var equip;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0 && status == 0) {
        cm.dispose();
        return;
    }
    if (mode <= 0 && status >= 1) {
        cm.dispose();
        return;
    }
    if (mode == 1) {
        status++;
    } else {
        status--;
    }

    // 直接从选择冶炼类型开始，跳过初始确认
    if (status == 0) {
        var selStr = "我喜欢你的作风！我们现在就开工吧。你想要冶炼哪种母矿？ #b";
        var options = ["精炼矿石", "精炼宝石", "精炼水晶矿石", "精炼稀有宝石", "制作材料", "高级矿石合成", "高等宝石合成"];
        for (var i = 0; i < options.length; i++) {
            selStr += "\r\n#L" + i + "# " + options[i] + "#l \r\n";
        }
        cm.sendSimple(selStr);
    } else if (status == 1 && mode == 1) {
        selectedType = selection;
        if (selectedType == 0) { //mineral refine
            var selStr = "那么，你想要提炼哪种矿石？#b";
            var minerals = ["#i4011000##t4011000#", "#i4011001##t4011001#", "#i4011002##t4011002#", "#i4011003##t4011003#", "#i4011004##t4011004#", "#i4011005##t4011005#", "#i4011006##t4011006#", "#i4011008##t4011008#"];
            for (var i = 0; i < minerals.length; i++) {
                selStr += "\r\n#L" + i + "# " + minerals[i] + "#l";
            }
            cm.sendSimple(selStr);
            equip = false;
        } else if (selectedType == 1) { //jewel refine
            var selStr = "那么，你想要提炼哪种宝石？#b";
            var jewels = ["#i4021000##t4021000#", "#i4021001##t4021001#", "#i4021002##t4021002#", "#i4021003##t4021003#", "#i4021004##t4021004#", "#i4021005##t4021005#", "#i4021006##t4021006#", "#i4021007##t4021007#", "#i4021008##t4021008#"];
            for (var i = 0; i < jewels.length; i++) {
                selStr += "\r\n#L" + i + "# " + jewels[i] + "#l";
            }
            cm.sendSimple(selStr);
            equip = false;
        } else if (selectedType == 2) { //Crystal refine
            var selStr = "水晶？这可真是稀有。别担心，我冶炼它们的手艺就像对矿石和宝石那样熟练。你想要冶炼哪种水晶？#b";
            var crystals = ["#i4005000##t4005000#", "#i4005001##t4005001#", "#i4005002##t4005002#", "#i4005003##t4005003#", "#i4005004##t4005004#"];
            for (var i = 0; i < crystals.length; i++) {
                selStr += "\r\n#L" + i + "# " + crystals[i] + "#l";
            }
            cm.sendSimple(selStr);
            equip = false;
        } else if (selectedType == 3) { //Crystal refine
            var selStr = "想制作稀有宝石吗？你想制作哪一种呢？#b";
            var items = ["#i4011007##t4011007#", "#i4021009##t4021009#", "#i4251200##t4251200#"];
            for (var i = 0; i < items.length; i++) {
                selStr += "\r\n#L" + i + "# " + items[i] + "#l";
            }
            cm.sendSimple(selStr);
            equip = false;
        } else if (selectedType == 4) { //Crystal refine
            var selStr = "材料吗？我有几种可以为你制作的材料……#b";
            var materials = ["使用树枝制作加工木材", "使用木块制作加工木材", "制作螺丝（15个）"];
            for (var i = 0; i < materials.length; i++) {
                selStr += "\r\n#L" + i + "# " + materials[i] + "#l";
            }
            cm.sendSimple(selStr);
            equip = false;
        } else if (selectedType == 5) { //Crystal refine
            cm.dispose();
            cm.openNpc(9900001, "高等宝石兑换");
        } else if (selectedType == 6) { //各种宝石
            cm.dispose();
            cm.openNpc(9900001, "高等宝石兑换2");
        }
    } else if (status == 2 && mode == 1) {
        selectedItem = selection;
        if (selectedType == 0) { //mineral refine
            var itemSet = [4011000, 4011001, 4011002, 4011003, 4011004, 4011005, 4011006, 4011008];
            var matSet = [4010000, 4010001, 4010002, 4010003, 4010004, 4010005, 4010006, 4010007];
            var matQtySet = [10, 10, 10, 10, 10, 10, 10, 10];
            var costSet = [270, 270, 270, 450, 450, 450, 720, 270];
            item = itemSet[selectedItem];
            mats = matSet[selectedItem];
            matQty = matQtySet[selectedItem];
            cost = costSet[selectedItem];
        } else if (selectedType == 1) { //jewel refine
            var itemSet = [4021000, 4021001, 4021002, 4021003, 4021004, 4021005, 4021006, 4021007, 4021008];
            var matSet = [4020000, 4020001, 4020002, 4020003, 4020004, 4020005, 4020006, 4020007, 4020008];
            var matQtySet = [10, 10, 10, 10, 10, 10, 10, 10, 10];
            var costSet = [450, 450, 450, 450, 450, 450, 450, 900, 2700];
            item = itemSet[selectedItem];
            mats = matSet[selectedItem];
            matQty = matQtySet[selectedItem];
            cost = costSet[selectedItem];
        } else if (selectedType == 2) { //Crystal refine
            var itemSet = [4005000, 4005001, 4005002, 4005003, 4005004];
            var matSet = [4004000, 4004001, 4004002, 4004003, 4004004];
            var matQtySet = [10, 10, 10, 10, 10];
            var costSet = [5000, 5000, 5000, 5000, 1000000];
            item = itemSet[selectedItem];
            mats = matSet[selectedItem];
            matQty = matQtySet[selectedItem];
            cost = costSet[selectedItem];
        } else if (selectedType == 3) { //Crystal refine
            var itemSet = [4011007, 4021009, 4251200];
            var matSet = [[4011000, 4011001, 4011002, 4011003, 4011004, 4011005, 4011006], [4021000, 4021001, 4021002, 4021003, 4021004, 4021005, 4021006, 4021007, 4021008], [4005000, 4005001, 4005002, 4005003, 4005004]];
            var matQtySet = [[1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1], [30, 30, 30, 30, 30]];
            var costSet = [10000, 15000, 0];
            item = itemSet[selectedItem];
            mats = matSet[selectedItem];
            matQty = matQtySet[selectedItem];
            cost = costSet[selectedItem];
        } else if (selectedType == 4) { //Crystal refine
            var itemSet = [4003001, 4003001, 4003000];
            var matSet = [4000003, 4000018, [4011000, 4011001]];
            var matQtySet = [10, 5, [1, 1]];
            var costSet = [0, 0, 0];
            item = itemSet[selectedItem];
            mats = matSet[selectedItem];
            matQty = matQtySet[selectedItem];
            cost = costSet[selectedItem];
        }
        var prompt = "想要制作#t" + item + "#，对吗？那么，你想制作多少？";
        cm.sendGetNumber(prompt, 1, 1, 100)
    } else if (status == 3 && mode == 1) {
        if (equip) {
            selectedItem = selection;
            qty = 1;
        } else {
            qty = (selection > 0) ? selection : (selection < 0 ? -selection : 1);
        }

        var prompt = "你想制作 ";
        if (qty == 1) {
            prompt += "一件 #t" + item + "#?";
        } else {
            prompt += qty + "件 #t" + item + "#?";
        }

        prompt += " 那么，请确认你准备好了相应材料，并且背包里有充足的空间。#b";

        if (mats instanceof Array) {
            for (var i = 0; i < mats.length; i++) {
                prompt += "\r\n#i" + mats[i] + "# " + matQty[i] * qty + " #t" + mats[i] + "#";
            }
        } else {
            prompt += "\r\n#i" + mats + "# " + matQty * qty + " #t" + mats + "#";
        }

        if (cost > 0) {
            prompt += "\r\n#i4031138# " + cost * qty + " 金币";
        }

        cm.sendYesNo(prompt);
    } else if (status == 4 && mode == 1) {
        var complete = true;
        var recvItem = item, recvQty;

        if (item >= 2060000 && item <= 2060002) //bow arrows
        {
            recvQty = 1000 - (item - 2060000) * 100;
        } else if (item >= 2061000 && item <= 2061002) //xbow arrows
        {
            recvQty = 1000 - (item - 2061000) * 100;
        } else if (item == 4003000)//screws
        {
            recvQty = 15 * qty;
        } else {
            recvQty = qty;
        }

        if (!cm.canHold(recvItem, recvQty)) {
            cm.sendOk("背包空间不足。");
        } else if (cm.getMeso() < cost * qty) {
            cm.sendOk("金币不足的话，我无法为你制作。");
        } else {
            if (mats instanceof Array) {
                for (var i = 0; complete && i < mats.length; i++) {
                    if (!cm.haveItem(mats[i], matQty[i] * qty)) {
                        complete = false;
                    }
                }
            } else {
                if (!cm.haveItem(mats, matQty * qty)) {
                    complete = false;
                }
            }
            if (!complete) {
                cm.sendOk("请确保材料足够，并且有足够的其他栏空间。");
            } else {
                if (mats instanceof Array) {
                    for (var i = 0; i < mats.length; i++) {
                        cm.gainItem(mats[i], -matQty[i] * qty);
                    }
                } else {
                    cm.gainItem(mats, -matQty * qty);
                }

                if (cost > 0) {
                    cm.gainMeso(-cost * qty);
                }

                cm.gainItem(recvItem, recvQty);
                cm.sendOk("东西都在这里，完成了。简直就是艺术品，你不这样认为吗？总之，如果还有其他需要，就再来找我吧。");
            }
        }

        cm.dispose();
    }
}
