// NPC 3003156 - 穆托
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
if (cm.getQuestStatus(-31320) == 1) {
            cm.completeQuest(-31320);
            cm.sendOk("夢幻三明治完成的那個瞬間！地面在搖晃，古拉的進攻開始了。快點去見族長里昂吧！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31319) == 1) {
            cm.completeQuest(-31319);
            cm.sendOk("終於到了決戰的瞬間。舔舔大師和西米雅將各自的料理呈現給武藤。究竟武藤的選擇會是如何呢？");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31318) == 1) {
            cm.completeQuest(-31318);
            cm.sendOk("GOOD BYE！啾啾艾爾蘭！");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(-31336) == 0) {
            cm.sendYesNo("將與卡歐的離別拋諸腦後，沿著奧術之河去找黑魔法師的途中，遇見了擋住奧術之河的可疑物體。\r\n\r\n#b接受任務：[阻隔的奧術之河]#k");
            status = 1336;
            return;
        }
 else if (cm.getQuestStatus(-31319) == 0 && cm.getQuestStatus(-31320) == 2) {
            cm.sendYesNo("終於到了決戰的瞬間。舔舔大師和西米雅將各自的料理呈現給武藤。究竟武藤的選擇會是如何呢？\r\n\r\n#b接受任務：[武藤的選擇]#k");
            status = 1319;
            return;
        }
 else if (cm.getQuestStatus(-31318) == 0 && cm.getQuestStatus(-31319) == 2) {
            cm.sendYesNo("多虧感動了武藤的三明治，武藤重新振作起來，自古拉手中保護了啾啾艾爾蘭的安全。來吧！現在是重新繼續面對黑魔法師的時候了。\r\n\r\n#b接受任務：[再見，啾啾艾爾蘭]#k");
            status = 1318;
            return;
        }
        cm.sendOk("你好！我是穆托。");
        cm.dispose();
    }
    else if (status == 1336) {
        cm.startQuest(-31336);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1319) {
        cm.startQuest(-31319);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 1318) {
        cm.startQuest(-31318);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 9999) {
        cm.warp(450003000);
        cm.dispose();
    }
}

// 注意：任務-31318完成後，Act.img.xml中已配置nextMap=450003000自動傳送
// 如需手動傳送選項，可在status==0的末尾添加：
// if (cm.getQuestStatus(-31318) == 2) { cm.sendSimple("要去拉克蘭嗎？\r\n#L0##b前往拉契爾恩#k"); status = 9999; return; }