/*
	物品:	2431151
	描述:	传送卷轴 - 传送至910700000
	适配:	北斗GMS083 物品脚本
*/

function start() {
    var player = im.getPlayer();

    // 传送至目标地图
    try {
        im.warp(105040300, 0);
    } catch (e) {
        player.dropMessage(5, "传送失败，请稍后再试。");
        im.dispose();
        return;
    }

    // 消耗一个物品
    im.gainItem(2431151, -1);

    im.dispose();
}
