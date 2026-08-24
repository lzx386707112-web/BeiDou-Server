// NPC 3003211 - 黑面具
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
if (cm.getQuestStatus(34322) == 1) {
            cm.completeQuest(34322);
            cm.sendOk("在舞會場遇見了黑面具。");
            cm.dispose(); return;
        }
        cm.sendOk("你好！我是黑面具。");
        cm.dispose();
    }
}