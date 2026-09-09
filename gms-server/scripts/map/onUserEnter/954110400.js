function start(ms) {
    var leftover = ms.getMap().countMonsters();
    var stage = Math.floor((ms.getMapId() % 1000) / 100) + 1;
    if (stage >= 6) {
        ms.playerMessage(5, "最终阶段：消灭所有怪物后走传送门离开。点休菲凯曼可以放弃或领奖。");
    } else {
        ms.playerMessage(5, "第 " + stage + " 阶段：消灭全部怪物后，走上方传送门进入下一关。点休菲凯曼可以离开；清空后也可以让他送你去下一关。还剩 " + leftover + " 只怪物。");
    }
}
