function enter(pi) {
	if(pi.isQuestCompleted(31177)&&!pi.isQuestCompleted(31178)){
		pi.playPortalSound();
        pi.warp(272010000, "sp");
	}else { 
    pi.playPortalSound();
    pi.warp(272000500, "sp");
	}
    return true;
}
