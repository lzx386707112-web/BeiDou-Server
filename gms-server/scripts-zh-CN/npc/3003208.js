// NPC 3003208 - 露希妲
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
if (cm.getQuestStatus(34331) == 1) {
            cm.completeQuest(34331);
            cm.sendOk("與露希妲的最終決戰！");
            cm.dispose(); return;
        }
        cm.sendOk("你好！我是露希妲。");
        cm.dispose();
    }
}