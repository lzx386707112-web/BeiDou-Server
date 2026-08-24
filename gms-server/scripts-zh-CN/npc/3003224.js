// NPC 3003224 - 舞會面具
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
if (cm.getQuestStatus(34325) == 1) {
            cm.completeQuest(34325);
            cm.sendOk("舞會場裡的面具似乎藏著什麼秘密…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34325) == 0 && cm.getQuestStatus(34324) == 2) {
            cm.sendYesNo("舞會場裡的面具似乎藏著什麼秘密…\r\n\r\n#b接受任務：[舞會面具]#k");
            status = 4325;
            return;
        }
        cm.sendOk("你好！我是舞會面具。");
        cm.dispose();
    }
    else if (status == 4325) {
        cm.startQuest(34325);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}