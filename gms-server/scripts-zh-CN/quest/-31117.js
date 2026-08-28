// -31117 (TMS 34419) - [星光之塔] 發現巨星的原石<5>
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("就如藏在泥土中的寶石一樣具有無比魅力的蒂雅！她絕對有成為巨星的可能性！將大發娛樂的名片遞給一路波折的歌手練習生#b蒂雅#k吧！"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("推薦蒂雅之後，新人組合確定以５人成員出道。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
