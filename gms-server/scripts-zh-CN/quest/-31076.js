// -31076 (TMS 34460) - [阿爾卡娜]與月光最近的地方
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("與月光最近的地方……，究竟在說什麼呢？再次與小精靈對話吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("一將草笛移道與月光最近的地方後，則開始回到原本的模樣，也發出了清脆的聲音。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
