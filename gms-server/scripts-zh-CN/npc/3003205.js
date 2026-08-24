// NPC 3003205 - 舞會場管理員
// 啾啾島/拉克蘭任務 NPC
var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) { cm.dispose(); return; }
    status++;

    if (status == 0) {
if (cm.getQuestStatus(34319) == 1) {
            cm.completeQuest(34319);
            cm.sendOk("前往拉契爾恩的舞會場吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34324) == 1) {
            cm.completeQuest(34324);
            cm.sendOk("再次前往舞會場吧。");
            cm.dispose(); return;
        }
        cm.sendOk("你好！我是舞會場管理員。");
        cm.dispose();
    }
}