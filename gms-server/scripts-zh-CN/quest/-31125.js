// -31125 (TMS 34411) - [星光之塔] 拜託找回散落的筆記
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("在#r星光之塔3樓奇特商店#k內遇見了少女#b佩里#k，就算周圍再怎麼混亂仍舊絲毫不受影響，反而使她更加耀眼。但是，她突然面露難色。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("雖然有收集到全部的#t4036021:#很好，不小心偷看到了內容。先把它拿給佩里吧！"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
