// NPC 3003153 - 哔比
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
if (cm.getQuestStatus(-31327) == 1 && cm.getItemCount(4034946) >= 20 && cm.getItemCount(4034947) >= 20) {
            cm.gainItem(4034946, -20);
            cm.gainItem(4034947, -20);
            cm.completeQuest(-31327);
            cm.sendOk("完成了啾樂森林的味道<1>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31326) == 1 && cm.getItemCount(4034948) >= 20 && cm.getItemCount(4034949) >= 20) {
            cm.gainItem(4034948, -20);
            cm.gainItem(4034949, -20);
            cm.completeQuest(-31326);
            cm.sendOk("完成了啾樂森林的味道<2>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31327) == 0 && cm.getQuestStatus(-31328) == 2) {
            cm.sendYesNo("大大是叫我尋找普利溫的清爽的鬃毛和火爆普利溫的辛辣的鬃毛。\r\n\r\n#b接受任務：[尋找啾樂森林的味道<1>]#k");
            status = 1327;
            return;
        }
 else if (cm.getQuestStatus(-31326) == 0 && cm.getQuestStatus(-31327) == 2) {
            cm.sendYesNo("大大要你去帶來半熟的果狼軟腳掌與全熟的利姆利姆軟腳掌。\r\n\r\n#b接受任務：[尋找啾樂森林的味道<2>]#k");
            status = 1326;
            return;
        }
        cm.sendOk("你好！我是哔比。");
        cm.dispose();
    }
    else if (status == 1327) {
        cm.startQuest(-31327);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1326) {
        cm.startQuest(-31326);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}