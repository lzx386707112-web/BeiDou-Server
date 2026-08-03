function enter(pi) {
	if(pi.isQuestCompleted(31178)){
		pi.playPortalSound();
        pi.warp(272000000, "west00");
	}else {
    pi.playPortalSound();
    pi.warp(272000600, "west00");
    }
	return true;
}
