// -31158 (TMS 34378) - [每日任務] 拉契爾恩的平安夜
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("大爺對這都市的慶典似乎還有些陌生。\r\n快去找找#r#m450003100:##k的#b#p3003209:##k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("每天透過#r#m450003100:##k的#b#p3003209:##k執行並接受#r3個#k委託之後，似乎就可以為充滿慶典的都市帶來和平的夜晚。

接受#b#p3003209:##k的請託，為夢之都市拉契爾恩帶來寧靜與和平吧。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
