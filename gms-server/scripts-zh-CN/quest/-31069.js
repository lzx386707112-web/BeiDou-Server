// -31069 (TMS 34467) - [阿爾卡娜]恢復樹藤豎琴1
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("透過隱藏在#r#m450005220##k的入口追上#b小精靈#k吧。

藤條豎琴旁長著的大樹阻擋了星光。樹木好像是隨著發出聲音的那端移動。

和在#r#m940200216##k的#b小精靈#k搭話，商量看看該怎麼辦吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("只用#t4036099:#似乎有些不夠。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
