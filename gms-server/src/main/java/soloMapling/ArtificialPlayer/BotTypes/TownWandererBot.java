package soloMapling.ArtificialPlayer.BotTypes;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotChatterSystem.BotChatter;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotDialogueHandler;
import soloMapling.ArtificialPlayer.BotFlavorSystem.BotFlavor;
import soloMapling.ArtificialPlayer.BotFlavorSystem.LevelUpCongrats;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotWanderSystem.BotWanderSystem;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;
import soloMapling.BotLogger;
import soloMapling.server.EventMessageSystem.EventBus;
import soloMapling.server.EventMessageSystem.EventType;
import soloMapling.server.EventMessageSystem.GameEvent;
import soloMapling.server.SoloMaplingUtilities;

public class TownWandererBot extends BotSM {
    private volatile WanderState wanderState = WanderState.RESET;
    private volatile boolean traveling;
    private int homeMapId = -1;
    private List<Integer> townFamily = List.of();
    private long lastMapChangeMs;
    private static final long MAP_CHANGE_COOLDOWN_MS = 90000;
    private final Random rng = new Random();

    private enum WanderState {
        RESET,
        IDLE,
        WANDER,
        EMOTE,
        CHANGE_MAP
    }

    public TownWandererBot(Character character) {
        super(character);
        this.dialoguePath = "TownWandererDialogue.yaml";
        this.botType = "TownWandererBot";
        EventBus.getInstance().subscribe(EventType.LEVEL_UP, this);
    }

    @Override
    public boolean isAvailableForAmbientActions() {
        return !traveling && !BotChatter.isEngaged(getChr());
    }

    @Override
    public void updateState() {
        Character chr;
        super.updateState();
        if (checkIfNotRunningOrPaused() || (chr = getChr()) == null || chr.getMap() == null) {
            return;
        }
        processQueuedEvents();
        switch (wanderState) {
            case RESET -> doReset();
            case IDLE -> decideNext();
            case WANDER -> {
                ensureRoaming();
                doRandomEmote();
                doRandomChat("WanderChat");
                wanderState = WanderState.IDLE;
            }
            case EMOTE -> {
                doRandomEmote();
                doRandomChat("EmoteReaction");
                wanderState = WanderState.IDLE;
            }
            case CHANGE_MAP -> doChangeMap();
        }
    }

    private void doReset() {
        if (homeMapId < 0) {
            homeMapId = getChr().getMapId();
            townFamily = discoverTownFamily(homeMapId);
        }
        ensureRoaming();
        wanderState = WanderState.IDLE;
    }

    private List<Integer> discoverTownFamily(int home) {
        return List.of(home);
    }

    private void decideNext() {
        BotFlavor.maybeExpress(this);
        BotChatter.maybeStartChatter(this);
        ensureRoaming();
        boolean cooled = System.currentTimeMillis() - lastMapChangeMs > MAP_CHANGE_COOLDOWN_MS;
        if (cooled && townFamily.size() > 1 && SoloMaplingUtilities.rollChanceInverse(12)) {
            wanderState = WanderState.CHANGE_MAP;
        } else if (SoloMaplingUtilities.rollChanceInverse(3)) {
            wanderState = WanderState.WANDER;
        } else if (SoloMaplingUtilities.rollChanceInverse(5)) {
            wanderState = WanderState.EMOTE;
        }
    }

    private void ensureRoaming() {
        Character chr = getChr();
        if (chr == null || traveling) {
            return;
        }
        if (!GCMovement.isMapObserved(chr.getMapId())) {
            BotWanderSystem.stop(chr);
            return;
        }
        if (!BotWanderSystem.isWandering(chr)) {
            BotWanderSystem.start(chr);
        }
    }

    private void doChangeMap() {
        Character chr = getChr();
        int dest = pickNextMap(townFamily, chr.getMapId());
        if (dest < 0) {
            wanderState = WanderState.IDLE;
            return;
        }
        doRandomChat("MapTransition");
        BotWanderSystem.stop(chr);
        traveling = true;
        lastMapChangeMs = System.currentTimeMillis();
        GCMovement.travel(chr, dest, ok -> traveling = false);
        wanderState = WanderState.IDLE;
    }

    private int pickNextMap(List<Integer> family, int currentMapId) {
        List<Integer> options = new ArrayList<>();
        for (int m : family) {
            if (m != currentMapId) {
                options.add(m);
            }
        }
        if (options.isEmpty()) {
            return -1;
        }
        return options.get(rng.nextInt(options.size()));
    }

    private void doRandomEmote() {
        if (SoloMaplingUtilities.rollChanceInverse(10)) {
            SocialCommands.BotEmote(getChr(), SoloMaplingUtilities.rollChanceInverse(2) ? 2 : 3);
        }
    }

    private void doRandomChat(String dialogueNode) {
        if (SoloMaplingUtilities.rollChanceInverse(20)) {
            try {
                String line = BotDialogueHandler.getRandomDialogueLine(this, dialogueNode);
                if (line != null) {
                    SocialCommands.BotSpeak(getChr(), line);
                }
            } catch (Exception ignored) {
            }
        }
    }

    @Override
    public void handleEvent(GameEvent event) {
        LevelUpCongrats.react(this, event);
    }

    @Override
    public synchronized void stopScheduledTask() {
        Character chr = getChr();
        if (chr != null) {
            BotChatter.forget(chr);
            BotWanderSystem.stop(chr);
            GCMovement.disable(chr);
        }
        super.stopScheduledTask();
        BotLogger.log("[TownWandererBot] stopped: " + (chr != null ? chr.getName() : "?"));
    }
}
