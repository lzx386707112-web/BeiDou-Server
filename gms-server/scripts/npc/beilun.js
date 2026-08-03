// root_qrcave.js — 深渊之门·贝伦剧情对话（北斗GMS083改写版）
// 由 ms.openNpc(1064001, "root_qrcave") 触发
//
// ⚠️ 原版脚本使用了以下API，北斗GMS083中均不存在，已全部移除：
//   npc_ChangeController, npc_SetSpecialAction, npc_LeaveField,
//   curNodeEventEnd, setInGameDirectionMode, inGameDirectionEvent_MoveAction,
//   inGameDirectionEvent_SetHideEffect, setStandAloneMode,
//   inGameDirectionEvent_AskAnswerTime, inGameDirectionEvent_PushMoveInfo,
//   inGameDirectionEvent_头顶图片, inGameDirectionEvent_OneTimeAction,
//   effect_OnUserEff, effect_Direction, sendNormalTalk
//
// ⚠️ 原版 sendNormalTalk(text, type, npcId) 可指定NPC 1064017(贝伦)头像
//   北斗GMS083 cm.sendNext() 无法指定其他NPC头像
//   NPC对话行用 cm.sendNext(text) 显示脚本NPC头像
//   玩家对话行用 cm.sendNext(text, 3) 显示玩家头像

var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == 0) {
        cm.dispose();
        return;
    }
    status++;
    if (status == 0) {
        cm.sendNext("这是什么地方……？", 3);
    } else if (status == 1) {
        cm.sendNext("愚蠢的人！为什么要反抗#r那个人#k的意志！");
    } else if (status == 2) {
        cm.sendNext("你，你是谁？！", 3);
    } else if (status == 3) {
        cm.sendNext("我是侍奉那位#r伟大的人#k的封印守护者#b贝伦#k。\r\n愚蠢的人，你为什么要到这里来，破坏#r那个人#k的心情？");
    } else if (status == 4) {
        cm.sendNext("封印守护者？\r\n将世界树封印起来的人是你吗？", 3);
    } else if (status == 5) {
        cm.sendNext("封印是#r那个人#k设下的。\r\n我只是按照#r那个人#k的命令，在这里守护封印。");
    } else if (status == 6) {
        cm.sendNext("#r那个人#k是指一只眼睛戴着眼罩的那个魔族吗？", 3);
    } else if (status == 7) {
        cm.sendNext("闭嘴！那个人可不是你能随便挂在嘴上的！\r\n在那位#r伟大的人#k的力量面前，你就像是一粒渺小的灰尘。\r\n总有一天，你也会跪在#r那个人#k的面前！");
    } else if (status == 8) {
        cm.sendNext("我不想和他战斗。\r\n和他一样都是魔族的恶魔猎手现在也成了我们的同伴。\r\n所以你们也应该和我们……\r\n\r\n（诶？等等...同伴？谁？恶魔猎手？为什么我会知道未来的事？！）", 3);
    } else if (status == 9) {
        cm.sendNext("肮脏的背叛者竟敢怂恿我们背叛#r那个人#k，看来你是活得不耐烦了！");
    } else if (status == 10) {
        cm.sendNext("看来光靠说话行不通。那就只能打败你，然后再获取情报了！", 3);
    } else if (status == 11) {
        cm.sendNext("凭你也想打败我？那就试试看吧！");
    } else if (status == 12) {
        cm.sendNext("我TM…………", 3);
    } else if (status == 13) {
        cm.sendNext("这么点程度就不行了吗？现在你知道自己有多无能了吧？");
    } else if (status == 14) {
        cm.sendNext("除了我之外，这里还有三个封印守护者。\r\n要想解开世界树的封印，必须把我们全部打倒才行。\r\n但是以你的力量，估计连一个都无法打倒。");
    } else if (status == 15) {
        cm.sendNext("现在你知道你自己是多么可悲的存在了！？\r\n这次暂且饶过你这卑贱的生命，别再踏入此处半步，我的仁慈是有限度的。");
    } else if (status == 16) {
        cm.forceCompleteQuest(30006);
        cm.warp(910700200, 0);
        cm.dispose();
    }
}
