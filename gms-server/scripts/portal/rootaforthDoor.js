function enter(pi) {
	if(pi.isQuestActive(30012)){
    pi.playPortalSound();
    pi.warp(105200800, "sp");
    return true;
	} else if(pi.haveItem(4033611)){
	pi.playPortalSound();
    pi.warp(105200800, "sp");
    return true;
	}else{
		pi.playerMessage(5, "你现在还没有资格进去。");
        return false;
	}
}
