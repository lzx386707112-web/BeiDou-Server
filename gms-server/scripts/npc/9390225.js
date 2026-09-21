var status = -1;
var routes = ["多尔切", "露娜", "罗萨", "赫尔", "里恩", "北方海域"];

function start() { status = -1; action(1, 0, 0); }

function action(mode, type, selection) {
    if (mode != 1) { cm.dispose(); return; }
    status++;
    var eim = cm.getEventInstance();
    if (eim == null) {
        cm.sendOk("当前没有正在进行的航海。");
        cm.dispose();
        return;
    }
    if (status == 0) {
        var route = eim.getIntProperty("route");
        var wave = eim.getIntProperty("wave");
        var waveCount = eim.getIntProperty("waveCount");
        var remaining = cm.getPlayer().getMap().countMonsters();
        var text = "#e航海状态#n\r\n航线：#b" + routes[route] + "#k\r\n";
        if (eim.getIntProperty("finished") != 0) {
            text += "状态：#b航线已完成#k\r\n";
        } else if (eim.getIntProperty("waveTransition") != 0) {
            text += "进度：第 " + wave + "/" + waveCount + " 波已清除\r\n下一波将在 2 秒后开始。\r\n";
        } else {
            text += "进度：第 " + (wave + 1) + "/" + waveCount + " 波\r\n剩余怪物：#r" + remaining + "#k\r\n";
        }
        text += "\r\n#L0##b离开本次航海#k#l";
        cm.sendSimple(text);
        return;
    }
    if (selection == 0) eim.removePlayer(cm.getPlayer());
    cm.dispose();
}
