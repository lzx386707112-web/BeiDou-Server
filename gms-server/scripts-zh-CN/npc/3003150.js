// NPC 3003150 - 瑞昂
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
if (cm.getQuestStatus(-31336) == 1) {
            cm.completeQuest(-31336);
            cm.sendOk("向利昂打聽啾啾艾爾蘭的狀況吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31335) == 0 && cm.getQuestStatus(-31336) == 2) {
            cm.sendYesNo("去找把你從武藤攻擊中救出來的獅子獸人－利昂，向他打聽啾啾艾爾蘭的狀況吧！\r\n\r\n#b接受任務：[歡迎來到啾啾艾爾蘭]#k");
            status = 1335;
            return;
        }
 else if (cm.getQuestStatus(-31320) == 0 && cm.getQuestStatus(-31321) == 2) {
            cm.sendYesNo("夢幻三明治完成的那個瞬間！地面在搖晃，古拉的進攻開始了。快點去見族長里昂吧！\r\n\r\n#b接受任務：[古拉的侵攻]#k");
            status = 1320;
            return;
        }
        cm.sendOk("你好！我是瑞昂。");
        cm.dispose();
    }
    else if (status == 1335) {
        cm.startQuest(-31335);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1320) {
        cm.startQuest(-31320);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}