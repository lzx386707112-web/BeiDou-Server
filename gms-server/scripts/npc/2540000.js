/**
 * @description 起源之塔 NPC（NpcId 2540000，艾丽西亚）
 *
 * 两种形态，靠事件实例属性 seedTower 区分：
 *   1) 塔内（eim.getProperty("seedTower") == "1"）—— 继续挑战 / 结束本次挑战
 *   2) 大厅（常驻于 992000000）—— 挑战入口 + 起源宝库目录：
 *      玩法说明 / 查看当前积分 / 积分商店 / 起源抽奖 / 奖池预览
 *
 * 积分货币「起源积分」存在 extend_value 表（角色扩展值）里，键名必须与
 * event/SeedTower20.js、BeiDouSpecial/起源之塔/*.js 完全一致，改名要一起改。
 *
 * 弹窗里的 #i4009930# 是道具图标，要求客户端 Item/Etc/0400.img 里存在该道具；
 * 5 个抽奖卷（4009930-4009934）由 tool/scripts/migration/seed_tower_rewards.py 生成。
 */
var 起源积分键 = "起源积分";
var 起源累计键 = "起源累计积分";
var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode != 1) {
        cm.dispose();
        return;
    }
    status++;
    var eim = cm.getEventInstance();
    if (status == 0) {
        if (eim && eim.getProperty("seedTower") == "1") {
            eim.invokeScriptFunction("progress", eim);
            cm.sendSimple("起源之塔\r\n#L0#继续挑战#l\r\n#L1#结束本次挑战#l");
        } else {
            cm.sendSimple(大厅菜单());
        }
        return;
    }
    if (eim && eim.getProperty("seedTower") == "1") {
        // 塔内分支保持原样：先 dispose 再结束挑战
        cm.dispose();
        if (selection == 1) eim.invokeScriptFunction("end", eim);
        return;
    }
    大厅选择(selection);
}

// ============================================================
// 大厅主菜单
// ============================================================
function 大厅菜单() {
    var 文本 = "#e#d【起源之塔】#k#n\r\n";
    文本 += "起源积分：#r" + 取数值(起源积分键) + "#k 分    #d累计：" + 取数值(起源累计键) + " 分#k\r\n";
    文本 += "#d----------------------------------------#k\r\n";
    文本 += "#L0##b[挑战前 20 层]#k#l\t#L1##b[返回射手村]#k#l\r\n";
    文本 += "\r\n#e#b── 起源宝库 ──#k#n\r\n";
    文本 += "#L2##i4009930# #b[玩法说明]#k#l\r\n";
    文本 += "#L3##i4009932# #b[查看当前积分]#k#l\r\n";
    文本 += "#L4##i4009931# #b[积分商店]#k#l\r\n";
    文本 += "#L5##i4009933# #b[起源抽奖]#k#l\r\n";
    文本 += "#L6##i4009934# #b[奖池预览]#k#l";
    return 文本;
}

// 每个分支自己决定收尾方式：openNpc 内部会 dispose，发文本的必须先 sendOk 再 dispose。
function 大厅选择(selection) {
    switch (selection) {
        case 0:// 挑战前 20 层
            cm.dispose();
            if (cm.getPlayer().getEventInstance() != null) {
                cm.getPlayer().dropMessage(5, "请先离开当前副本。");
                return;
            }
            var manager = cm.getEventManager("SeedTower20");
            if (!manager || manager.getName() != "SeedTower20" || !manager.startInstance(cm.getPlayer())) {
                cm.getPlayer().dropMessage(5, "起源之塔暂无空闲实例，请稍后重试。");
            }
            return;
        case 1:// 返回射手村
            cm.dispose();
            cm.warp(100000000);
            return;
        case 2:// 玩法说明
            openNpc("起源之塔/玩法说明");
            return;
        case 3:// 查看当前积分
            显示积分();
            return;
        case 4:// 积分商店
            openNpc("起源之塔/积分商店");
            return;
        case 5:// 起源抽奖
            openNpc("起源之塔/抽奖");
            return;
        case 6:// 奖池预览
            openNpc("起源之塔/奖池预览");
            return;
        default:
            cm.sendOk("该功能暂不支持，敬请期待！");
            cm.dispose();
    }
}

function 显示积分() {
    var 文本 = "#e#d【起源积分】#k#n\r\n";
    文本 += "#d----------------------------------------#k\r\n";
    文本 += "当前积分：#r" + 取数值(起源积分键) + "#k 分\r\n";
    文本 += "累计获得：#b" + 取数值(起源累计键) + "#k 分\r\n";
    文本 += "#d----------------------------------------#k\r\n";
    文本 += "#d每通过 1 层得 2 分，20 层全通共 40 分；\r\n";
    文本 += "时间耗尽退出按已通过层数 ×2 发放，主动退出不发。#k";
    cm.sendOk(文本);
    cm.dispose();
}

// ============================================================
// 工具
// ============================================================
function 取数值(键) {
    return parseInt(cm.getCharacterExtendValue(键)) || 0;
}

function openNpc(scriptName) {
    // 与 BeiDouSpecial 系列脚本同一套路：先 dispose 再打开目标脚本
    // （AbstractPlayerInteraction.openNpc 内部还会再 dispose 一次）
    cm.dispose();
    cm.openNpc(9900001, scriptName);
}
