// NPC 3003209 - 神秘的少女
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
if (cm.getQuestStatus(34301) == 1) {
            cm.completeQuest(34301);
            cm.sendOk("跟居民對話之後，發現這座城市不太正常。去問問那個少女吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34302) == 1) {
            cm.completeQuest(34302);
            cm.sendOk("這座城市似乎陷入了某種不正常的狀態。少女似乎知道些什麼。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34305) == 1) {
            cm.completeQuest(34305);
            cm.sendOk("與防毒面具會合吧。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34316) == 1) {
            cm.completeQuest(34316);
            cm.sendOk("居民們似乎開始清醒了…");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34318) == 1) {
            cm.completeQuest(34318);
            cm.sendOk("找到了第二個音樂盒。");
            cm.dispose(); return;
        }
 else if (cm.getQuestStatus(34300) == 0) {
            cm.sendYesNo("已抵達正在舉行慶典的城市。但不太對勁。跟住民們對話看看吧。\r\n\r\n#b接受任務：[長期進行慶典的都市]#k");
            status = 4300;
            return;
        }
 else if (cm.getQuestStatus(34301) == 0 && cm.getQuestStatus(34300) == 2) {
            cm.sendYesNo("跟居民對話之後，發現這座城市不太正常。去問問那個少女吧。\r\n\r\n#b接受任務：[夢想與幻想的都市]#k");
            status = 4301;
            return;
        }
 else if (cm.getQuestStatus(34302) == 0 && cm.getQuestStatus(34301) == 2) {
            cm.sendYesNo("這座城市似乎陷入了某種不正常的狀態。少女似乎知道些什麼。\r\n\r\n#b接受任務：[無法脫離的慶典都市]#k");
            status = 4302;
            return;
        }
 else if (cm.getQuestStatus(34309) == 0 && cm.getQuestStatus(34308) == 2) {
            cm.sendYesNo("夢中似乎聽見了什麼聲音…去調查一下吧。\r\n\r\n#b接受任務：[夢中聽見的聲音]#k");
            status = 4309;
            return;
        }
 else if (cm.getQuestStatus(34310) == 0 && cm.getQuestStatus(34309) == 2) {
            cm.sendYesNo("那個聲音似乎是音樂盒發出的…\r\n\r\n#b接受任務：[音樂盒的聲音？]#k");
            status = 4310;
            return;
        }
 else if (cm.getQuestStatus(34317) == 0 && cm.getQuestStatus(34316) == 2) {
            cm.sendYesNo("露希妲在尋找的惡夢到底是什麼…\r\n\r\n#b接受任務：[露希妲尋找的惡夢]#k");
            status = 4317;
            return;
        }
 else if (cm.getQuestStatus(34326) == 0 && cm.getQuestStatus(34325) == 2) {
            cm.sendYesNo("好像墜落到了什麼地方…\r\n\r\n#b接受任務：[墜落]#k");
            status = 4326;
            return;
        }
        cm.sendOk("你好！我是神秘的少女。");
        cm.dispose();
    }
    else if (status == 4300) {
        cm.startQuest(34300);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4301) {
        cm.startQuest(34301);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4302) {
        cm.startQuest(34302);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4309) {
        cm.startQuest(34309);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4310) {
        cm.startQuest(34310);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4317) {
        cm.startQuest(34317);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
    else if (status == 4326) {
        cm.startQuest(34326);
        cm.sendOk("任務已接受！");
        cm.dispose();
    }
}