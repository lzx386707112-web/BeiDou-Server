// NPC 3003239 - 伊莉莎白
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
if (cm.getQuestStatus(34311) == 0 && cm.getQuestStatus(34310) == 2) {
            cm.sendYesNo("伊莉莎白不見了，去調查一下吧。\r\n\r\n#b接受任務：[消失的伊莉莎白1]#k");
            status = 4311;
            return;
        }
        cm.sendOk("你好！我是伊莉莎白。");
        cm.dispose();
    }
    else if (status == 4311) {
        cm.startQuest(34311);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}