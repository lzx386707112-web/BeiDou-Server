// -31119 (TMS 34417) - [星光之塔] 歌曲的主人是？
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("露比，薩菲，佩里，亞咪。４名新人歌手候補一起聚集在赫一的辦公室。現場瀰漫著緊張的氣息，馬上#b赫一#k就要#b#e發表重大消息#n#k，到底赫一的新曲會由哪一個歌手詮釋呢？"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("深深苦惱後，赫一決定成立新人團體組合！當大家沉浸於這個好消息時，要幫忙準備出道的蒂雅卻不見蹤影。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
