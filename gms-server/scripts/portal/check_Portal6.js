function enter(pi) {
	if(pi.isQuestActive(31178)){
		pi.openNpc(2144000,"AkayrumFS");
	} else if(pi.isQuestCompleted(31178)){
		pi.playPortalSound();
        pi.warp(272010100, "west00");
	} else {
		pi.	playerMessage(5, "你现在还不能过去");
	}
    return true;
}
