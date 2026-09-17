var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode !== 1) {
        cm.dispose();
        return;
    }
    status++;
    if (status === 0) {
        var state = cm.isMonsterVacActive() ? "#g已开启#k" : "#r已关闭#k";
        cm.sendSimple(
            "怪物吸星大法当前" + state + "。\r\n\r\n" +
                "#L0##b开启吸怪#l\r\n" +
                "#L1##b关闭吸怪#l"
        );
        return;
    }
    if (selection === 0) {
        if (cm.isMonsterVacActive()) {
            cm.sendOk("吸怪已经开启，无需重复打开。");
        } else {
            cm.startMonsterVac();
        }
    } else if (selection === 1) {
        if (!cm.isMonsterVacActive()) {
            cm.sendOk("吸怪本来就是关闭的。");
        } else {
            cm.stopMonsterVac();
        }
    }
    cm.dispose();
}
