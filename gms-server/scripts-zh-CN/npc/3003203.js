// NPC 3003203 - 居民
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
if (cm.getQuestStatus(34310) == 1) {
            cm.completeQuest(34310);
            cm.sendOk("那個聲音似乎是音樂盒發出的…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34316) == 0 && cm.getQuestStatus(34315) == 2) {
            cm.sendYesNo("居民們似乎開始清醒了…\r\n\r\n#b接受任務：[醒來的居民們]#k");
            status = 4316;
            return;
        }
        cm.sendOk("你好！我是居民。");
        cm.dispose();
    }
    else if (status == 4316) {
        cm.startQuest(34316);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}