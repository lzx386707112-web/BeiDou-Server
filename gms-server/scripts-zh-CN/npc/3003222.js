// NPC 3003222 - 時間塔守衛
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
if (cm.getQuestStatus(34328) == 1) {
            cm.completeQuest(34328);
            cm.sendOk("來到了惡夢時間塔的2樓。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34328) == 0 && cm.getQuestStatus(34327) == 2) {
            cm.sendYesNo("來到了惡夢時間塔的2樓。\r\n\r\n#b接受任務：[惡夢時間塔2樓]#k");
            status = 4328;
            return;
        }
        cm.sendOk("你好！我是時間塔守衛。");
        cm.dispose();
    }
    else if (status == 4328) {
        cm.startQuest(34328);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}