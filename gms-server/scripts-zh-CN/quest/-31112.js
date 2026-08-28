// -31112 (TMS 34424) - [星光之塔] 吉他上的音樂精靈
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("根據赫一的說法，團員們狀況變得奇怪，是在演奏過練習室的吉他之後發生的，去調查一下#b練習室的吉他#k吧。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("成功擊退練習室吉他上的音樂精靈，聽說音樂精靈只會出現在新人歌手面前，現在應該沒事了吧？雖然以為這只是口耳相傳的流言。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
