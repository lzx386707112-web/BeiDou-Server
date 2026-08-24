// NPC 3003202 - 調查員
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
if (cm.getQuestStatus(34300) == 1) {
            cm.completeQuest(34300);
            cm.sendOk("已抵達正在舉行慶典的城市。但不太對勁。跟住民們對話看看吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34306) == 1) {
            cm.completeQuest(34306);
            cm.sendOk("前往拉契爾恩市中心吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34307) == 1) {
            cm.completeQuest(34307);
            cm.sendOk("調查誰是'甦醒者'吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34307) == 0 && cm.getQuestStatus(34306) == 2) {
            cm.sendYesNo("調查誰是'甦醒者'吧。\r\n\r\n#b接受任務：[誰是'甦醒者'呢？]#k");
            status = 4307;
            return;
        }
 else if (cm.getQuestStatus(34308) == 0 && cm.getQuestStatus(34307) == 2) {
            cm.sendYesNo("繼續調查'甦醒者'的身份。\r\n\r\n#b接受任務：[誰是'甦醒者'呢？2]#k");
            status = 4308;
            return;
        }
        cm.sendOk("你好！我是調查員。");
        cm.dispose();
    }
    else if (status == 4307) {
        cm.startQuest(34307);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4308) {
        cm.startQuest(34308);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}