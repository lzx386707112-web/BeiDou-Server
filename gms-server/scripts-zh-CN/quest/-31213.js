// -31213 (TMS 34323) - [拉契爾恩]淨化者
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("必須和在#m450003440#的防毒面具說話。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("黑色面具順利逃走，但防毒面具留了下來。 就算負傷也要繼續找音樂盒。 "); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
