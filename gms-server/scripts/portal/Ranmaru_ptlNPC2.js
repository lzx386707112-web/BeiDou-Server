function enter(pi) {
    if (!pi.haveItem(4000697, 1)) {
        pi.playerMessage(5, "需要持有森兰丸挑战门票才能进入。");
        return false;
    }
    pi.openNpc(9130145);
    return true;
}
