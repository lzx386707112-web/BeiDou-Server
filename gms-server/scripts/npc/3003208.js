// NPC 3003208 - Lucid expedition guide / Arcane River quest NPC
var status = -1;

function start() {
    status = -1;
    action(1, 0, 0);
}

function action(mode, type, selection) {
    if (mode <= 0) { cm.dispose(); return; }
    status++;

    if (status == 0) {
        if (cm.getMapId() == 450004000) {
            cm.dispose();
            cm.openNpc(9900001, "露希妲远征");
            return;
        }
        if (cm.getQuestStatus(34331) == 1) {
            cm.completeQuest(34331);
            cm.sendOk("The final battle with Lucid awaits.");
            cm.dispose();
            return;
        }
        cm.sendOk("The boundary between dream and reality is growing thin.");
        cm.dispose();
    }
}
