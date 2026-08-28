// -31084 (TMS 34452) - [阿爾卡娜]花瓣跳舞之際
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("依照小精靈所說的，原本這附近沒有光之漩渦。在精靈之樹開花的時分。小精靈這樣說了。那是光之漩渦，究竟跟變得兇暴的精靈有沒有關係呢？"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("精靈之樹和精靈們在和諧的森林樂曲中過著幸福的日子。但某一天，從森林樂曲消失時開始破壞了和諧。而與森林樂曲產生共鳴的精靈之樹也失去了力氣且也產生了光之漩渦。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
