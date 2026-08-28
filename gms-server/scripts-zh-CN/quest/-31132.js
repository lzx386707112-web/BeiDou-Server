// -31132 (TMS 34404) - [星光之塔] 請讓我成為選拔歌手的星探吧！
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("…在放棄之前先問問自己還有什麼解決辦法吧！或許跟#b#p1052203##k稍微談談，會出現不錯的答案。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("出發之前聽祕書#b#p1052212##k說明徵選歌手相關的基本事項吧！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
