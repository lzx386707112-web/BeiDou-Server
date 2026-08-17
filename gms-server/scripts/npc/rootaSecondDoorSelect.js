let status = -1;

function start() {
    cm.sendSimple("Choose the Root Abyss garden to enter.\r\n#b#L0#Von Bon's normal garden#l\r\n#L1#Von Bon's advanced garden#l");
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        if (selection === 0) {
            cm.warp(105200200, "sp");
        } else if (selection === 1) {
            cm.warp(105200600, "sp");
        }
    }
    cm.dispose();
}
