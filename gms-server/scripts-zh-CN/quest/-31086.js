// -31086 (TMS 34450) - [阿爾卡娜]再見，惡夢的都市
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("覆蓋著拉契爾恩的紅色霧氣難以輕易的散去。到完全的消失看來需要一些時間。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("覆蓋著拉契爾恩的紅色霧氣難以輕易的散去。到完全的消失看來需要一些時間。 聽到遠方熟悉的聲音而過去確認，飛魚們都回來了。搭乘飛魚隨著天空的路線掉到了拉契爾恩。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
