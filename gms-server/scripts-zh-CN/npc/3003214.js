// NPC 3003214 - 聲音
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
if (cm.getQuestStatus(34309) == 1) {
            cm.completeQuest(34309);
            cm.sendOk("夢中似乎聽見了什麼聲音…去調查一下吧。");
            cm.dispose(); return;
        }
        cm.sendOk("你好！我是聲音。");
        cm.dispose();
    }
}