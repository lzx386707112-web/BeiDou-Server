// NPC 3003154 - 哔美
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
if (cm.getQuestStatus(-31325) == 1 && cm.getItemCount(4034950) >= 20 && cm.getItemCount(4034951) >= 20) {
            cm.gainItem(4034950, -20);
            cm.gainItem(4034951, -20);
            cm.completeQuest(-31325);
            cm.sendOk("完成了艾勒溪谷的味道<1>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31324) == 1 && cm.getItemCount(4034952) >= 20 && cm.getItemCount(4034953) >= 20) {
            cm.gainItem(4034952, -20);
            cm.gainItem(4034953, -20);
            cm.completeQuest(-31324);
            cm.sendOk("完成了艾勒溪谷的味道<2>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31325) == 0 && cm.getQuestStatus(-31326) == 2) {
            cm.sendYesNo("逼米要你帶回綠貓魚的結實魚鰭與藍貓魚的酸酸魚鰭。\r\n\r\n#b接受任務：[尋找艾勒溪谷的味道<1>]#k");
            status = 1325;
            return;
        }
 else if (cm.getQuestStatus(-31324) == 0 && cm.getQuestStatus(-31325) == 2) {
            cm.sendYesNo("逼米需要拉伊托特的乾巴巴背殼和隊長拉伊托特的軟綿綿背殼。\r\n\r\n#b接受任務：[尋找艾勒溪谷的味道<2>]#k");
            status = 1324;
            return;
        }
        cm.sendOk("你好！我是哔美。");
        cm.dispose();
    }
    else if (status == 1325) {
        cm.startQuest(-31325);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1324) {
        cm.startQuest(-31324);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}