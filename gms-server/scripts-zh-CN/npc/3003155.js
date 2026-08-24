// NPC 3003155 - 小石
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
if (cm.getQuestStatus(-31323) == 1 && cm.getItemCount(4034954) >= 20 && cm.getItemCount(4034955) >= 20) {
            cm.gainItem(4034954, -20);
            cm.gainItem(4034955, -20);
            cm.completeQuest(-31323);
            cm.sendOk("完成了藍色鯨魚山的味道<1>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31322) == 1 && cm.getItemCount(4034956) >= 20 && cm.getItemCount(4034957) >= 20) {
            cm.gainItem(4034956, -20);
            cm.gainItem(4034957, -20);
            cm.completeQuest(-31322);
            cm.sendOk("完成了藍色鯨魚山的味道<2>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31323) == 0 && cm.getQuestStatus(-31324) == 2) {
            cm.sendYesNo("小石說需要克利拉的翅膀碎片和鳥鯊的翅膀碎片。\r\n\r\n#b接受任務：[尋找藍色鯨魚山的味道<1>]#k");
            status = 1323;
            return;
        }
 else if (cm.getQuestStatus(-31322) == 0 && cm.getQuestStatus(-31323) == 2) {
            cm.sendYesNo("小石最後要求你帶來族長克利拉的結實翅膀碎片和族長鳥鯊的酸甜翅膀碎片。\r\n\r\n#b接受任務：[尋找藍色鯨魚山的味道<2>]#k");
            status = 1322;
            return;
        }
        cm.sendOk("你好！我是小石。");
        cm.dispose();
    }
    else if (status == 1323) {
        cm.startQuest(-31323);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1322) {
        cm.startQuest(-31322);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}