var status = 0;

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode == -1 || mode == 0) {
        cm.dispose();
        return;
    }

    if (status == 0) {
        cm.sendSimple("#b#L0#剑之地#l\r\n#L1#火焰之地#l\r\n#L2#风暴之地#l\r\n#L3#黑暗之地#l\r\n#L4#闪电之地#l");
        status = 1;
    } else if (status == 1) {
        cm.warp(271030201 + selection, 0);
        cm.dispose();
    }
}
