let status = -1;

function start() {
    cm.sendYesNo("进入皮埃尔混沌庭院？");
}

function action(mode, type, selection) {
    if (mode === 1) {
        cm.warp(105200500, "sp");
    }
    cm.dispose();
}
