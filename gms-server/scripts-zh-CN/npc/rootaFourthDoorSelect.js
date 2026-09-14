let status = -1;

function start() {
    cm.sendYesNo("进入贝伦混沌庭院？");
}

function action(mode, type, selection) {
    if (mode === 1) {
        cm.warp(105200800, "sp");
    }
    cm.dispose();
}
