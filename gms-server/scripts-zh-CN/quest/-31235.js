// -31235 (TMS 34301) - [拉契爾恩]夢想與幻想的都市
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext(" 見到露希妲後雖然經歷了絕處逢生的危機，但救出了防毒面具和老爺。 老爺好像要跟你說明什麼。  "); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("這個地方是夢之都拉契爾恩。 我遇到的正是夢的操縱者露希妲。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
