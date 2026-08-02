/**
 * @description 发色选择脚本
 */
var status = -1;
var newHairs = [];
// 所需点券数量
const DRAW_COST = 6000;
//当[当前发色不显示=true]时,预览不显示当前发色
var 当前发色不显示 = true;
var ItemConstants = Java.type("org.gms.constants.inventory.ItemConstants");

function start() {
    action(1, 0, 0)
}

function action(mode, type, selection) {
    if (mode === 1) {
        status++;
    } else if (mode === -1) {
        status--;
    } else {
        cm.dispose();
        return;
    }
    if (status === 0) {
        发色展示();
    } else if (status == 1) {
        设置发色(selection);
    } else {
        cm.dispose();
    }
}

function 发色展示() {
    newHairs = Array();
    var currentHair = cm.getPlayer().getHair();
    if (!ItemConstants.isNewHair(currentHair)) {
        cm.sendOk("该发型不支持改变颜色，请先更换发型！");
        cm.dispose();
        return;
    }
    var currentBaseHair = parseInt(currentHair / 10) * 10;
    for (var i = 0; i <= 7; i++) {
        let newHairsId = currentBaseHair + i;
        if (ItemConstants.isNewHair(newHairsId) && cm.itemExists(newHairsId)) {
            if (当前发色不显示 && cm.isCosmeticEquipped(newHairsId)) {
                continue;
            }
            newHairs.push(newHairsId);
        }
    }
    // 判断newHairs是否为空
    if (newHairs.length === 0) {
        cm.sendOk("该发型不支持改变颜色，请先更换发型！");
        cm.dispose(); // 结束对话
    } else {
        cm.sendStyle("挑选一款发色吧！#b需要消耗" + DRAW_COST + "点卷！", newHairs);
    }
}

function 设置发色(selection) {
    const player = cm.getPlayer();
    if (selection < 0 || selection >= newHairs.length) {
        cm.sendOk("该发色不可用，请重新选择。");
        cm.dispose();
        return;
    }
    // 1.检查点卷是否足够
    if (cm.getPlayer().getCashShop().getCash(1) < DRAW_COST) {
        cm.sendOk("你的点卷不足" + DRAW_COST + "。");
        cm.dispose();
        return;
    }
    // 2.扣除点卷
    player.getCashShop().gainCash(1, -DRAW_COST);//点券
    // 3. 点券足够，执行对应操作
    cm.setHair(newHairs[selection]);
    cm.sendOk(`发型已变更,从现在开始你是世界上最靓的崽!!\r\n已扣除${DRAW_COST}点券。`);
    cm.dispose();
}
