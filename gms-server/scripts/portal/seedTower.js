function enter(pi) {
    var chr=pi.getPlayer(), eim=chr.getEventInstance(), name=pi.getPortal().getName();
    if(chr.getMapId()==992000000) {
        if(name=="ptOut") {pi.warp(100000000,0);return true;}
        if(name=="go1F" && !eim) {
            var manager=pi.getEventManager("SeedTower20");
            if(manager && manager.getName()=="SeedTower20") return manager.startInstance(chr);
        }
        return false;
    }
    if(!eim || eim.getProperty("seedTower")!="1") {pi.warp(992000000,0);return true;}
    return !!eim.invokeScriptFunction("seedPortal",eim,chr,name);
}
