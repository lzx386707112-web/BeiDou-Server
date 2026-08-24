// NPC 3003216 - 時間塔管理員
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
if (cm.getQuestStatus(34326) == 1) {
            cm.completeQuest(34326);
            cm.sendOk("好像墜落到了什麼地方…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34327) == 1) {
            cm.completeQuest(34327);
            cm.sendOk("來到了惡夢時間塔的1樓。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34327) == 0 && cm.getQuestStatus(34326) == 2) {
            cm.sendYesNo("來到了惡夢時間塔的1樓。\r\n\r\n#b接受任務：[惡夢時間塔1樓]#k");
            status = 4327;
            return;
        }
        cm.sendOk("你好！我是時間塔管理員。");
        cm.dispose();
    }
    else if (status == 4327) {
        cm.startQuest(34327);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}