function act() {
    var eim=rm.getEventInstance();
    if(eim && eim.getProperty("seedTower")=="1")
        eim.invokeScriptFunction("seedCoconut",eim,rm.getPlayer(),rm.getReactor());
}
