let status = -1;

function start() {
    cm.sendYesNo("进入血腥女王混沌庭院？");
}

function action(mode, type, selection) {
    if (mode === 1) {
        cm.warp(105200700, "sp");
    }
    cm.dispose();
}
