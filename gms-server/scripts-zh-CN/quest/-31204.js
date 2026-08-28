// -31204 (TMS 34332) - [拉契爾恩]吃飽的武藤
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("充滿飽腹感的武藤，現在應該會想讓路\r了吧？跟武藤搭話，移動到#r下一個地區#k\r看看吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("充滿飽腹感的武藤，現在應該會想讓路\r了吧？跟武藤搭話，移動到#r下一個地區#k\r看看吧。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
