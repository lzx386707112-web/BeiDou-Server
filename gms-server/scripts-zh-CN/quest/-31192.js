// -31192 (TMS 34344) - [拉契爾恩] 夢中夢
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("來寫一封信，向聯盟傳達在拉契爾恩獲得的關於奧術之河的情報吧。將寫好的信摺成紙船，然後放在#b拉契爾恩河下游#k的#b平靜水面#k上漂走應該就行了。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("紙船逆流而上，沿著拉契爾恩的河水漂向了遠方。…這艘紙船真的能到達聯盟嗎？如果能到達那就太好了…"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
