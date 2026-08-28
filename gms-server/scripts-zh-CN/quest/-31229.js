// -31229 (TMS 34307) - [拉契爾恩]誰是'甦醒者'呢？
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("防毒面具正在市中心裡等你。 見到他後要找出「甦醒者」並保護他們。 "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("就算跟居民們講話，也很難確認誰是「甦醒者」。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
