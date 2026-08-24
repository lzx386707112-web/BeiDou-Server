// NPC 3003206 - 淨化者
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
if (cm.getQuestStatus(34323) == 1) {
            cm.completeQuest(34323);
            cm.sendOk("淨化者出現了。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34323) == 0 && cm.getQuestStatus(34322) == 2) {
            cm.sendYesNo("淨化者出現了。\r\n\r\n#b接受任務：[淨化者]#k");
            status = 4323;
            return;
        }
 else if (cm.getQuestStatus(34324) == 0 && cm.getQuestStatus(34323) == 2) {
            cm.sendYesNo("再次前往舞會場吧。\r\n\r\n#b接受任務：[再次前往舞會場]#k");
            status = 4324;
            return;
        }
        cm.sendOk("你好！我是淨化者。");
        cm.dispose();
    }
    else if (status == 4323) {
        cm.startQuest(34323);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4324) {
        cm.startQuest(34324);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}