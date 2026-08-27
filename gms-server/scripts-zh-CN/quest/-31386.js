// 任務 -31386 (TMS 34150) - [每日任務]找出30個安息抑制劑
var status = -1;

function start(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("取得30個#t4034936#，交給位在#b安息的洞窟#k區域某處的調查團員#b潔娜#k吧！ 安息的洞窟區域的部分怪物有#t4034936#。\r\n\r\n#b接受任務？#k");
    } else if (status == 1) {
        qm.forceStartQuest();
        qm.sendOk("任務已接受！完成後回來找我吧。");
        qm.dispose();
    }
}

function end(mode, type, selection) {
    if (mode <= 0) { qm.dispose(); return; }
    status++;
    if (status == 0) {
        qm.sendYesNo("找到30個#t4034936#，交給位在#b安息的洞窟#k區域某處的調查團員#b蘿娜#k吧！\r\n\r\n#b完成任務？#k");
    } else if (status == 1) {
        qm.forceCompleteQuest();
        qm.sendOk("辛苦了！謝謝你的幫忙。");
        qm.dispose();
    }
}
