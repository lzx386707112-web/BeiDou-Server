// NPC 3003241 - 舞會場侍者
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
if (cm.getQuestStatus(34320) == 1) {
            cm.completeQuest(34320);
            cm.sendOk("進入舞會場需要符合服儀要求。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34320) == 0 && cm.getQuestStatus(34319) == 2) {
            cm.sendYesNo("進入舞會場需要符合服儀要求。\r\n\r\n#b接受任務：[服儀要求]#k");
            status = 4320;
            return;
        }
        cm.sendOk("你好！我是舞會場侍者。");
        cm.dispose();
    }
    else if (status == 4320) {
        cm.startQuest(34320);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}