// -31118 (TMS 34418) - [星光之塔] 尋找蒂雅
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("要幫忙準備出道的祕書#b蒂雅#k不見蹤影。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("從練習室傳出某人的歌聲，歌聲的主人不是別人，正是祕書蒂雅。還以為自己已經放棄歌手之路，但卻無法放下自己的夢想。重新開始夢想的蒂雅，在熄燈的練習室內卻是如此閃耀。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
