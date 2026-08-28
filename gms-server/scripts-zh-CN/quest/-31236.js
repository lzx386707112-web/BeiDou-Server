// -31236 (TMS 34300) - [拉契爾恩]長期進行慶典的都市
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("已抵達正在舉行慶典的城市。 但不太對勁。跟住民們對話看看吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("已抵達正在舉行慶典的城市。 但不太對勁。 就算跟居民說話，他們也只重覆說著奇怪的話。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
