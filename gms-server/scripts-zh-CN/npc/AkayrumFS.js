/**
 * 十字猎人·阿卡伊勒分身 副本入口 NPC
 * 单人副本，基于 Level 阶段式对话框架改写
 * 原脚本：action(d,c,b) 模式，status==0 先 dispose 再逻辑（错误消息玩家看不到）
 */

var isRepeat = true;
var EventName = 'AkayrumFSB';
var EventLevel = 255;
var PQLog = '阿卡伊勒 分身';

var entryMap = 272010000;    // 事件启动时玩家进入的初始地图
var exitMap = 272010000;     // 玩家未能完成事件时被传送至此地图
var recruitMap = entryMap;   // 玩家必须在此地图上才能开始此事件
var clearMap = entryMap;     // 玩家成功完成事件后被传送至此地图

function start() {
    // 不在入口地图时，先传送过去并结束对话
    if (cm.getMapId() != entryMap) {
        cm.warp(entryMap, 0);
        cm.dispose();
        return;
    }

    var em = cm.getEventManager(EventName);
    if (em == null) {
        cm.sendOkLevel('', '配置文件不存在，请联系管理员。');
        cm.dispose();
        return;
    }

    cm.sendSelectLevel('', '我感受到#b阿卡伊勒#k的气息就在里面，但是又好像没有那么强大。你准备好了吗？\r\n\r\n#L0##b讨伐#l\r\n#L1#离开#l#k');
}

function level() {
    cm.dispose();
}
function levelnull() {
    cm.dispose();
}
function leveldispose() {
    cm.dispose();
}

function level0() {
    cm.sendNextLevel('0_1', '那就交给你了，祝你武运昌隆！');
}

function level0_1() {
    var em = cm.getEventManager(EventName);
    if (em == null) {
        cm.sendOkLevel('', '配置文件不存在，请联系管理员。');
        cm.dispose();
        return;
    }

    // 替代: em.getNumberProperty("state") → parseInt(em.getProperty("state"))
    var state = parseInt(em.getProperty("state") || "0");

    if (state == 0) {
        // 单人副本：直接传入玩家对象，无需组队
        em.startInstance(cm.getPlayer());
        try {
            em.setProperty("PQLog", PQLog);
        } catch (e) {
            // PQLog 跟踪机制可能不同，忽略
        }
    } else {
        cm.sendOkLevel('', '好像已经有人在进行尝试了，换其他频道尝试吧。');
    }
    cm.dispose();
}

function level1() {
    cm.dispose();
}

