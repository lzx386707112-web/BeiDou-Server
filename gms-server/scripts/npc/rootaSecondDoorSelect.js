let status = -1;

function start() {
    cm.sendYesNo("进入半半混沌庭院？");
}

function action(mode, type, selection) {
    if (mode === 1) {
        cm.warp(105200600, "sp");
    }
    cm.dispose();
}
