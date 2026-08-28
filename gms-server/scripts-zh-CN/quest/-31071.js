// -31071 (TMS 34465) - [阿爾卡娜]樹藤豎琴的狀態
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("重新回到夥伴身邊是否有解開一些誤會呢？再次向樹木的精靈搭話吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("精靈之中原本特別喜愛精靈之樹的樹木的精靈不知道為什麼會對於救回精靈之樹感到如此悲觀？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
