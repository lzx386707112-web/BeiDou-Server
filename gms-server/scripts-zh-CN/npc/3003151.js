// NPC 3003151 - 西米雅
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
if (cm.getQuestStatus(-31332) == 1) {
            cm.completeQuest(-31332);
            cm.sendOk("試吃最厲害的廚師舔舔大師推崇的特製料理！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31331) == 1) {
            cm.completeQuest(-31331);
            cm.sendOk("有個食物的香味直衝鼻腔內。跟著食物的味道去看看吧！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31330) == 1) {
            cm.completeQuest(-31330);
            cm.sendOk("跟著香味來到了村莊後面僻靜的地方。那裡有個裝著清潔工服裝的西米雅，以及在後頭跟著她的小雞三兄妹。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31329) == 1 && cm.getItemCount(4034943) >= 20) {
            cm.gainItem(4034943, -20);
            cm.completeQuest(-31329);
            cm.sendOk("完成了五色園林的味道<1>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31328) == 1 && cm.getItemCount(4034944) >= 20 && cm.getItemCount(4034945) >= 20) {
            cm.gainItem(4034944, -20);
            cm.gainItem(4034945, -20);
            cm.completeQuest(-31328);
            cm.sendOk("完成了五色園林的味道<2>！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31321) == 1 && cm.getItemCount(4034958) >= 1) {
            cm.gainItem(4034958, -1);
            cm.completeQuest(-31321);
            cm.sendOk("完成了抓住不足2%的那個味道吧！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31331) == 0 && cm.getQuestStatus(-31332) == 2) {
            cm.sendYesNo("有個食物的香味直衝鼻腔內。跟著食物的味道去看看吧！\r\n\r\n#b接受任務：[跟隨美味的味道]#k");
            status = 1331;
            return;
        }
 else if (cm.getQuestStatus(-31330) == 0 && cm.getQuestStatus(-31331) == 2) {
            cm.sendYesNo("跟著香味來到了村莊後面僻靜的地方。那裡有個裝著清潔工服裝的西米雅，以及在後頭跟著她的小雞三兄妹。\r\n\r\n#b接受任務：[廚房助手西米亞]#k");
            status = 1330;
            return;
        }
 else if (cm.getQuestStatus(-31329) == 0 && cm.getQuestStatus(-31330) == 2) {
            cm.sendYesNo("消滅大角鳳梨獸後收集辣辣角吧！\r\n\r\n#b接受任務：[尋找五色園林的味道<1>]#k");
            status = 1329;
            return;
        }
 else if (cm.getQuestStatus(-31328) == 0 && cm.getQuestStatus(-31329) == 2) {
            cm.sendYesNo("去處理猶娜娜和雷娜娜，收集油膩膩皮和酸甜皮吧！\r\n\r\n#b接受任務：[尋找五色園林的味道<2>]#k");
            status = 1328;
            return;
        }
 else if (cm.getQuestStatus(-31321) == 0 && cm.getQuestStatus(-31322) == 2) {
            cm.sendYesNo("據說只要有食人植物啾樂樹的果實，無論什麼料理都能擁有最棒的美味。去把啾樂樹給抓來吧！\r\n\r\n#b接受任務：[抓住不足2%的那個味道吧]#k");
            status = 1321;
            return;
        }
        cm.sendOk("你好！我是西米雅。");
        cm.dispose();
    }
    else if (status == 1331) {
        cm.startQuest(-31331);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1330) {
        cm.startQuest(-31330);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1329) {
        cm.startQuest(-31329);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1328) {
        cm.startQuest(-31328);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1321) {
        cm.startQuest(-31321);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}