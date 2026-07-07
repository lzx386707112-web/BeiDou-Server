var status = -1;

function start(mode, type, selection) {
    if (mode == -1) {
        qm.dispose();
    } else {
        if (mode == 0 && type > 0) {
            qm.dispose();
            return;
        }

        if (mode == 1) {
            status++;
        } else {
            status--;
        }

        if (status == 0) {
           qm.sendNext("骑士团要塞的动向好像不太寻常，似乎在计划着什么...");
        }else if (status == 1) {
            qm.sendOk("嗯...我需要帮助...");
        }else if (status == 2) {
            qm.forceCompleteQuest();
			qm.gainExp(7000);
            qm.dispose();
        }
    }
}
function isAllSubquestsDone() {
    for (var i = 31124; i < 31125; i++) {
        if (!qm.isQuestCompleted(i)) {
            return false;
        }
    }

    return true;
}

