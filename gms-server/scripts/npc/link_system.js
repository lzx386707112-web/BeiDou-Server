var showingResult = false;

function start() {
    showLinkMenu();
}

function action(mode, type, selection) {
    if (mode < 1) {
        if (showingResult) {
            showingResult = false;
            showLinkMenu();
        } else {
            cm.dispose();
        }
        return;
    }

    if (showingResult) {
        showingResult = false;
        showLinkMenu();
        return;
    }
    if (selection == -1) {
        cm.dispose();
        return;
    }

    showingResult = true;
    cm.sendNext(cm.linkSystemAdd(selection) + "\r\n\r\n点击下一步返回Link槽位。");
}

function showLinkMenu() {
    cm.sendSimple(cm.linkSystemOverview());
}
