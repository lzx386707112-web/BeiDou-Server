// -31127 (TMS 34409) - [星光之塔] …邀請，失敗！？
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("總是面帶笑容，擁有能讓人充滿活力的魅力！薩菲一定有成為明星的資質！將大發娛樂公司的名片遞交給#r薩菲#k吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("給薩菲聆聽赫一的新歌之後，不知道為什麼她的心似乎開始有所動搖…重新在邀請一次看看吧！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
