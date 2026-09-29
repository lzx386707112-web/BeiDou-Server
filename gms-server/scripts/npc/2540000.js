var status = -1;
function start() { action(1,0,0); }
function action(mode,type,selection) {
    if(mode!=1) {cm.dispose();return;}
    status++;
    var eim=cm.getEventInstance();
    if(status==0) {
        if(eim && eim.getProperty("seedTower")=="1") {
            eim.invokeScriptFunction("progress",eim);
            cm.sendSimple("起源之塔\r\n#L0#继续挑战#l\r\n#L1#结束本次挑战#l");
        } else cm.sendSimple("起源之塔\r\n#L0#挑战前 20 层#l\r\n#L1#返回射手村#l");
        return;
    }
    cm.dispose();
    if(eim && eim.getProperty("seedTower")=="1") {
        if(selection==1) eim.invokeScriptFunction("end",eim);
    } else if(selection==1) cm.warp(100000000);
    else {
        if(cm.getPlayer().getEventInstance()!=null) {cm.getPlayer().dropMessage(5,"请先离开当前副本。");return;}
        var manager=cm.getEventManager("SeedTower20");
        if(!manager || manager.getName()!="SeedTower20" || !manager.startInstance(cm.getPlayer()))
            cm.getPlayer().dropMessage(5,"起源之塔暂无空闲实例，请稍后重试。");
    }
}
