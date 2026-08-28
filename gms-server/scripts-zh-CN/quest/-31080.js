// -31080 (TMS 34456) - [阿爾卡娜]賦予草笛生命力2
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("正傳送生命力時，原還在想草笛會不會就這樣暫時的活過來但突然又枯萎了。 難道生命力不足嗎？和小精靈對話吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("和剛剛相同，短暫的回覆後馬上又枯萎了。難道無法永遠活過來嗎？"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
