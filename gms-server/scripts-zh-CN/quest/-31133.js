// -31133 (TMS 34403) - [星光之塔] 無法不哼上一曲的歡樂旋律
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("之前怎麼搖都叫不醒的#p1052203#突然大叫'腦海出現旋律了！'，但他看起來還是昏昏沉沉的，先去找祕書兼打雜的#b#p1052212##k問問看事情的始末吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("#p1052203#雖然總是表現的自暴自棄，但他就連睡覺的時候也會不自覺地唱起歌曲，由此可見他並沒有完全放棄音樂這條路…."); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
