// NPC 3003220 - 音樂盒
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
if (cm.getQuestStatus(34317) == 1) {
            cm.completeQuest(34317);
            cm.sendOk("露希妲在尋找的惡夢到底是什麼…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34318) == 0 && cm.getQuestStatus(34317) == 2) {
            cm.sendYesNo("找到了第二個音樂盒。\r\n\r\n#b接受任務：[第二個音樂盒]#k");
            status = 4318;
            return;
        }
        cm.sendOk("你好！我是音樂盒。");
        cm.dispose();
    }
    else if (status == 4318) {
        cm.startQuest(34318);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}