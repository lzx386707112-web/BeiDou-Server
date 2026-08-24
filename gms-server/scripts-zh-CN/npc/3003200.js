// NPC 3003200 - 黑面具
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
if (cm.getQuestStatus(34331) == 0 && cm.getQuestStatus(34330) == 2) {
            cm.sendYesNo("與露希妲的最終決戰！\r\n\r\n#b接受任務：[決戰]#k");
            status = 4331;
            return;
        }
        cm.sendOk("你好！我是黑面具。");
        cm.dispose();
    }
    else if (status == 4331) {
        cm.startQuest(34331);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}