// -31227 (TMS 34309) - [拉契爾恩]夢中聽見的聲音 
var status = -1;
function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendNext("因為被淨化者追趕，就回到了祕密據點。 要跟老爺說才行。"); }
    else { qm.forceStartQuest(); qm.dispose(); }
}
function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) { qm.sendOk("蝦面具想起了音樂盒的聲音。"); }
    else { qm.forceCompleteQuest(); qm.dispose(); }
}
