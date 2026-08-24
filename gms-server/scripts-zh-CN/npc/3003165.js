// NPC 3003165 - 吃饱的武藤
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
if (cm.getQuestStatus(34332) == 1) {
            cm.completeQuest(34332);
            cm.sendOk("武藤吃飽了！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34332) == 0 && cm.getQuestStatus(34300) == 2) {
            cm.sendYesNo("武藤吃飽了！\r\n\r\n#b接受任務：[吃飽的武藤]#k");
            status = 4332;
            return;
        }
        cm.sendOk("你好！我是吃饱的武藤。");
        cm.dispose();
    }
    else if (status == 4332) {
        cm.startQuest(34332);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}