// -31081 (TMS 34455) - [阿爾卡娜]賦予草笛生命力1
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("草笛枯萎了。要如何變活原來的樣子呢？和小精靈對話看看吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("正傳送生命力時，原還在想草笛會不會就這樣暫時的活過來但突然又枯萎了。難道是生命力不足的關係嗎？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
