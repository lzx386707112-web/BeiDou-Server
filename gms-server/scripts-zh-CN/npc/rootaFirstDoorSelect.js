let status = -1;

function start() {
    cm.sendSimple("请选择要进入的鲁塔比斯庭院。\r\n#b#L0#皮埃尔普通庭院#l\r\n#L1#皮埃尔进阶庭院#l");
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        if (selection === 0) {
            cm.warp(105200100, "sp");
        } else if (selection === 1) {
            cm.warp(105200500, "sp");
        }
    }
    cm.dispose();
}
