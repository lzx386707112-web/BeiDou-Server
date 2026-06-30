/*
    Adobis - Chaos Zakum expedition starter.
*/

var status = 0;
var expedition;
var expedMembers;
var player;
var em;
const ExpeditionType = Java.type('org.gms.server.expeditions.ExpeditionType');
const exped = ExpeditionType.CHAOS_ZAKUM;
var expedName = "ChaosZakum";
var expedBoss = "Chaos Zakum";
var expedMap = "Chaos Zakum's Altar";
var expedItem = 4001017;

var list = "What would you like to do?#b\r\n\r\n#L1#View current Expedition members#l\r\n#L2#Start the fight!#l\r\n#L3#Stop the expedition.#l";

function start() {
    action(1, 0, 0);
}

function action(mode, type, selection) {
    player = cm.getPlayer();
    expedition = cm.getExpedition(exped);
    em = cm.getEventManager("ChaosZakum");

    if (mode == -1 || mode == 0) {
        cm.dispose();
        return;
    }

    if (status == 0) {
        if (player.getLevel() < exped.getMinLevel() || player.getLevel() > exped.getMaxLevel()) {
            cm.sendOk("You do not meet the criteria to battle " + expedBoss + "!");
            cm.dispose();
        } else if (expedition == null) {
            cm.sendSimple("#e#b<Expedition: " + expedBoss + ">\r\n#k#n" + em.getProperty("party") + "\r\n\r\nWould you like to assemble a team to take on #r" + expedBoss + "#k?\r\n#b#L1#Lets get this going!#l\r\n#L2#No, I think I'll wait a bit...#l");
            status = 1;
        } else if (expedition.isLeader(player)) {
            if (expedition.isInProgress()) {
                cm.sendOk("Your expedition is already in progress.");
                cm.dispose();
            } else {
                cm.sendSimple(list);
                status = 2;
            }
        } else if (expedition.isRegistering()) {
            if (expedition.contains(player)) {
                cm.sendOk("You have already registered for the expedition. Please wait for #r" + expedition.getLeader().getName() + "#k to begin it.");
            } else {
                cm.sendOk(expedition.addMember(player));
            }
            cm.dispose();
        } else if (expedition.isInProgress()) {
            if (expedition.contains(player)) {
                var eim = em.getInstance(expedName + player.getClient().getChannel());
                if (eim != null && eim.getIntProperty("canJoin") == 1) {
                    eim.registerPlayer(player);
                } else {
                    cm.sendOk("Your expedition already started the battle against " + expedBoss + ".");
                }
            } else {
                cm.sendOk("Another expedition has already challenged " + expedBoss + ".");
            }
            cm.dispose();
        }
    } else if (status == 1) {
        if (selection == 1) {
            if (!cm.haveItem(expedItem)) {
                cm.sendOk("As the expedition leader, you must have a #b#t" + expedItem + "##k to battle " + expedBoss + "!");
                cm.dispose();
                return;
            }

            expedition = cm.getExpedition(exped);
            if (expedition != null) {
                cm.sendOk("Someone has already started registering an expedition. Try joining them!");
                cm.dispose();
                return;
            }

            var res = cm.createExpedition(exped);
            if (res == 0) {
                cm.sendOk("The #r" + expedBoss + " Expedition#k has been created.\r\n\r\nTalk to me again to view the current team, or start the fight!");
            } else if (res > 0) {
                cm.sendOk("Sorry, you've already reached the quota of attempts for this expedition. Try again another day.");
            } else {
                cm.sendOk("An unexpected error occurred when starting the expedition. Please try again later.");
            }
        } else {
            cm.sendOk("Sure, not everyone's up to challenging " + expedBoss + ".");
        }
        cm.dispose();
    } else if (status == 2) {
        if (selection == 1) {
            if (expedition == null) {
                cm.sendOk("The expedition could not be loaded.");
                cm.dispose();
                return;
            }
            expedMembers = expedition.getMemberList();
            var size = expedMembers.size();
            if (size == 1) {
                cm.sendOk("You are the only member of the expedition.");
                cm.dispose();
                return;
            }
            var text = "The following members make up your expedition (Click on them to expel them):\r\n";
            text += "\r\n\t\t1." + expedition.getLeader().getName();
            for (var i = 1; i < size; i++) {
                text += "\r\n#b#L" + (i + 1) + "#" + (i + 1) + ". " + expedMembers.get(i).getValue() + "#l\n";
            }
            cm.sendSimple(text);
            status = 6;
        } else if (selection == 2) {
            var min = exped.getMinSize();
            var size = expedition.getMemberList().size();
            if (size < min) {
                cm.sendOk("You need at least " + min + " players registered in your expedition.");
                cm.dispose();
                return;
            }

            cm.sendOk("The expedition will begin and you will now be escorted to the #b" + expedMap + "#k.");
            status = 4;
        } else if (selection == 3) {
            const PacketCreator = Java.type('org.gms.util.PacketCreator');
            player.getMap().broadcastMessage(PacketCreator.serverNotice(6, expedition.getLeader().getName() + " has ended the expedition."));
            cm.endExpedition(expedition);
            cm.sendOk("The expedition has now ended.");
            cm.dispose();
        }
    } else if (status == 4) {
        if (em == null) {
            cm.sendOk("The event could not be initialized.");
            cm.dispose();
            return;
        }

        em.setProperty("leader", player.getName());
        em.setProperty("channel", player.getClient().getChannel());
        if (!em.startInstance(expedition)) {
            cm.sendOk("Another expedition has already challenged " + expedBoss + ".");
            cm.dispose();
            return;
        }
        cm.dispose();
    } else if (status == 6) {
        if (selection > 0) {
            var banned = expedMembers.get(selection - 1);
            expedition.ban(banned);
            cm.sendOk("You have banned " + banned.getValue() + " from the expedition.");
            cm.dispose();
        } else {
            cm.sendSimple(list);
            status = 2;
        }
    }
}
