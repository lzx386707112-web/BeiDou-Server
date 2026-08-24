// NPC 3003235 - 伊莉莎白
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
if (cm.getQuestStatus(34311) == 1) {
            cm.completeQuest(34311);
            cm.sendOk("伊莉莎白不見了，去調查一下吧。");
            cm.dispose(); return;
        }
        cm.sendOk("你好！我是伊莉莎白。");
        cm.dispose();
    }
}