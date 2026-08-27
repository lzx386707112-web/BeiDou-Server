// NPC 3003104 - 蘿娜：消逝的旅途與反轉城市每日任務
var status = -1;
var selectedQuestId = 0;

var dailyQuests = {
    0: [-31406, "擊退200隻喜悅艾爾達斯"],
    1: [-31405, "擊退200隻憤怒艾爾達斯"],
    2: [-31404, "擊退200隻悲傷的艾爾達斯"],
    3: [-31403, "擊退200隻歡樂艾爾達斯"],
    4: [-31402, "擊退200隻岩石艾爾達斯"],
    5: [-31401, "擊退200隻火焰艾爾達斯"],
    6: [-31400, "擊退200隻強悍的靈魂艾爾達斯"],
    7: [-31399, "擊退200隻安息艾爾達斯"],
    10: [-31397, "收集50個喜悅艾爾達斯樣本"],
    11: [-31396, "收集50個憤怒艾爾達斯樣本"],
    12: [-31395, "收集50個悲傷的艾爾達斯樣本"],
    13: [-31394, "收集50個歡樂艾爾達斯樣本"],
    14: [-31393, "收集50個岩石艾爾達斯樣本"],
    15: [-31392, "收集50個火焰艾爾達斯樣本"],
    16: [-31391, "收集50個強悍的靈魂艾爾達斯樣本"],
    17: [-31390, "收集50個安息艾爾達斯樣本"],
    20: [-31388, "找出30個忘卻抑制劑"],
    21: [-31387, "找出30個消失抑制劑"],
    22: [-31386, "找出30個安息抑制劑"],
    30: [-26481, "擊退特拉200隻"],
    31: [-26480, "擊退蒙托200隻"],
    32: [-26479, "擊退搜索型T無人機A型200隻"],
    33: [-26478, "擊退搜索型T無人機B型200隻"],
    34: [-26477, "擊退戰鬥型T無人機A型200隻"],
    35: [-26476, "擊退戰鬥型T無人機B型200隻"],
    36: [-26475, "擊退殲滅型T無人機A型200隻"],
    37: [-26474, "擊退殲滅型T無人機B型200隻"],
    38: [-26473, "收集T-boy的零件50個"]
};

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) {
        cm.dispose();
        return;
    }
    status++;

    if (status == 0) {
        if (cm.getQuestStatus(-31408) == 0 && cm.getQuestStatus(-31416) == 2) {
            cm.sendYesNo("我是為了調查消逝的旅途而來的時間神官。#ho#，你能幫助我們破解這個空間的謎題嗎？");
            status = 100;
            return;
        }
        if (cm.getQuestStatus(-31408) == 1) {
            cm.sendOk("謝謝你。整理好每日調查內容後，我會再告訴你。");
            status = 299;
            return;
        }
        if (cm.getQuestStatus(-31408) == 2 && cm.getQuestStatus(-31407) == 0) {
            cm.sendNext("我要告訴你有關每日調查任務的內容。");
            status = 200;
            return;
        }
        if (cm.getQuestStatus(-31416) != 2) {
            cm.sendOk("完成消逝的旅途調查之旅後再來找我吧。");
            cm.dispose();
            return;
        }
        if (cm.getQuestStatus(-31407) != 2) {
            cm.sendOk("請先完成每日任務引導。");
            cm.dispose();
            return;
        }

        for (var key in dailyQuests) {
            var activeQuestId = dailyQuests[key][0];
            if (cm.getQuestStatus(activeQuestId) == 1) {
                cm.completeQuest(activeQuestId);
                if (cm.getQuestStatus(activeQuestId) == 2) {
                    cm.sendOk("辛苦了！任務已完成。\r\n\r\n#i1712001:# #t1712001:# 已經發放給你了。");
                } else {
                    cm.sendOk("尚未達成任務條件，完成後再來找我吧。");
                }
                cm.dispose();
                return;
            }
        }

        var menu = "#b#e每日調查任務#n#k\r\n\r\n";
        for (var option in dailyQuests) {
            if (cm.getQuestStatus(dailyQuests[option][0]) == 0) {
                menu += "#L" + option + "#" + dailyQuests[option][1] + "#l\r\n";
            }
        }
        cm.sendSimple(menu);
        return;
    }

    if (status == 300) {
        cm.completeQuest(-31408);
        cm.dispose();
        return;
    }
    if (status == 101) {
        cm.startQuest(-31408);
        cm.sendOk("謝謝你。往後請協助我們完成每日調查。");
        cm.dispose();
        return;
    }
    if (status == 201) {
        cm.sendNextPrev("每天可從我這裡接受調查任務，完成後會獲得#i1712001:# #t1712001:#。");
        return;
    }
    if (status == 202) {
        cm.startQuest(-31407);
        cm.completeQuest(-31407);
        cm.sendOk("引導到此為止，重新和我對話即可選擇任務。");
        cm.dispose();
        return;
    }

    if (status == 1) {
        var selected = dailyQuests[selection];
        if (selected == null) {
            cm.dispose();
            return;
        }
        promptDailyQuest(selected[0], selected[1]);
        return;
    }
    if (status == 2 && selectedQuestId != 0) {
        cm.startQuest(selectedQuestId);
        cm.sendOk("任務已接受！完成後再來找我吧。");
        cm.dispose();
        return;
    }
    cm.dispose();
}

function promptDailyQuest(questId, description) {
    selectedQuestId = questId;
    cm.sendYesNo(description + "。\r\n\r\n#b接受任務？#k");
}
