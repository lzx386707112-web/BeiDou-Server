// NPC 3003218 - 黑面具
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
if (cm.getQuestStatus(34322) == 0 && cm.getQuestStatus(34321) == 2) {
            cm.sendYesNo("在舞會場遇見了黑面具。\r\n\r\n#b接受任務：[黑面具]#k");
            status = 4322;
            return;
        }
        cm.sendOk("你好！我是黑面具。");
        cm.dispose();
    }
    else if (status == 4322) {
        cm.startQuest(34322);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}