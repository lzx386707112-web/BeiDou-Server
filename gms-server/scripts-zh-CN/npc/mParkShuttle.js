/**
 * 9071003 / mParkShuttle — Monster Park bus.
 * Lobby: leave to Twilight Perion. Free Market (and other maps): enter the park lobby.
 */

var status = -1;

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
        if (cm.getMapId() == 951000000) {
            cm.sendYesNo("要乘坐怪物公园公车离开这里吗？");
        } else {
            cm.sendYesNo("要乘坐怪物公园公车前往怪物公园吗？");
        }
        return;
    }
    if (cm.getMapId() == 951000000) {
        cm.warp(273000000, 0);
    } else {
        cm.warp(951000000, 0);
    }
    cm.dispose();
}
