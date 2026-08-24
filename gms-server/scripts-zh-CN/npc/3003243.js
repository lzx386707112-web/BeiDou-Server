// NPC 3003243 - 瘋狂居民
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
if (cm.getQuestStatus(34321) == 1) {
            cm.completeQuest(34321);
            cm.sendOk("舞會場裡的居民似乎都瘋了…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34321) == 0 && cm.getQuestStatus(34320) == 2) {
            cm.sendYesNo("舞會場裡的居民似乎都瘋了…\r\n\r\n#b接受任務：[瘋狂的舞會場居民]#k");
            status = 4321;
            return;
        }
        cm.sendOk("你好！我是瘋狂居民。");
        cm.dispose();
    }
    else if (status == 4321) {
        cm.startQuest(34321);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}