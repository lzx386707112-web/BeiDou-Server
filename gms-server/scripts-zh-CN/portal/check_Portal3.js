function enter(pi) {
	 if (pi.isQuestActive(31175) && !pi.isQuestCompleted(31176)) {
		 pi.playPortalSound();
         pi.warp(272000410, 2);
    } else {
    pi.playPortalSound();
    pi.warp(272000400, "west00");
   
}
 return true;
}
