// NPC 3003201 - 不夜城守衛
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
if (cm.getQuestStatus(34305) == 0 && cm.getQuestStatus(34304) == 2) {
            cm.sendYesNo("與防毒面具會合吧。\r\n\r\n#b接受任務：[會合]#k");
            status = 4305;
            return;
        }
 else if (cm.getQuestStatus(34306) == 0 && cm.getQuestStatus(34305) == 2) {
            cm.sendYesNo("前往拉契爾恩市中心吧。\r\n\r\n#b接受任務：[前往市中心]#k");
            status = 4306;
            return;
        }
 else if (cm.getQuestStatus(34319) == 0 && cm.getQuestStatus(34318) == 2) {
            cm.sendYesNo("前往拉契爾恩的舞會場吧。\r\n\r\n#b接受任務：[前往舞會場]#k");
            status = 4319;
            return;
        }
        cm.sendOk("你好！我是不夜城守衛。");
        cm.dispose();
    }
    else if (status == 4305) {
        cm.startQuest(34305);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4306) {
        cm.startQuest(34306);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4319) {
        cm.startQuest(34319);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}