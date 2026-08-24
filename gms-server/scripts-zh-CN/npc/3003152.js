// NPC 3003152 - 舔舔大師
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
if (cm.getQuestStatus(-31335) == 1) {
            cm.completeQuest(-31335);
            cm.sendOk("去找把你從武藤攻擊中救出來的獅子獸人－利昂，向他打聽啾啾艾爾蘭的狀況吧！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31334) == 1) {
            cm.completeQuest(-31334);
            cm.sendOk("能讓武藤移動的唯一辦法就只有製作出武藤想吃的美食。去見見啾啾艾爾蘭最厲害的廚師「舔舔大師」吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31333) == 1 && cm.getItemCount(4034942) >= 20) {
            cm.gainItem(4034942, -20);
            cm.completeQuest(-31333);
            cm.sendOk("完成了舔舔大師的特製料理！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31334) == 0 && cm.getQuestStatus(-31335) == 2) {
            cm.sendYesNo("能讓武藤移動的唯一辦法就只有製作出武藤想吃的美食。去見見啾啾艾爾蘭最厲害的廚師「舔舔大師」吧。\r\n\r\n#b接受任務：[頂尖料理師哈大師]#k");
            status = 1334;
            return;
        }
 else if (cm.getQuestStatus(-31333) == 0 && cm.getQuestStatus(-31334) == 2) {
            cm.sendYesNo("舔舔大師指使人幫忙完成他自己的特製料理…\r\n\r\n#b接受任務：[哈大師的特製料理]#k");
            status = 1333;
            return;
        }
 else if (cm.getQuestStatus(-31332) == 0 && cm.getQuestStatus(-31333) == 2) {
            cm.sendYesNo("試吃最厲害的廚師舔舔大師推崇的特製料理！\r\n\r\n#b接受任務：[這個味道是？！]#k");
            status = 1332;
            return;
        }
        cm.sendOk("你好！我是舔舔大師。");
        cm.dispose();
    }
    else if (status == 1334) {
        cm.startQuest(-31334);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1333) {
        cm.startQuest(-31333);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1332) {
        cm.startQuest(-31332);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}