package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotLogic;
import soloMapling.ArtificialPlayer.BotMessagingSystem.CharacterStorage;
import soloMapling.ArtificialPlayer.BotMovementSystem.PlayerReaction;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.server.ExecutorServiceManager;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPlayerReaction.class */
final class BotPlayerReaction {
    private static final String REACT_NODE = "PlayerReaction";
    private static final int DETECT_WIDTH = 300;
    private static final int DETECT_HEIGHT = 200;
    private static final int IGNORE_WEIGHT = 55;
    private static final int STOP_WEIGHT = 15;
    private static final int WALK_WEIGHT = 30;
    private static final long SCAN_INTERVAL_MS = 1500;
    private static final long STOP_PAUSE_MIN_MS = 900;
    private static final long STOP_PAUSE_MAX_MS = 2500;
    private static final long REACT_COOLDOWN_MIN_MS = 120000;
    private static final long REACT_COOLDOWN_MAX_MS = 240000;
    private static final Map<Integer, Long> PLAYER_REACT_UNTIL = new ConcurrentHashMap();

    private BotPlayerReaction() {
    }

    static void maybeReact(BotMovementState entry, Character bot) {
        long nowMs = System.currentTimeMillis();
        if (nowMs < entry.nextPlayerScanMs || entry.reactingUntilMs > nowMs) {
            return;
        }
        entry.nextPlayerScanMs = nowMs + SCAN_INTERVAL_MS;
        List<Character> players = BotLogic.getRealPlayersInRange(bot, DETECT_WIDTH, DETECT_HEIGHT);
        for (Character player : players) {
            if (player != null && !onCooldown(player.getId(), nowMs)) {
                switch (AnonymousClass1.$SwitchMap$org$gms$soloMapling$ArtificialPlayer$BotMovementSystem$PlayerReaction$ReactionType[PlayerReaction.rollReaction(IGNORE_WEIGHT, STOP_WEIGHT, WALK_WEIGHT).ordinal()]) {
                    case 2:
                        speak(bot, player);
                        markReacted(player.getId(), nowMs);
                        return;
                    case 3:
                        reactStop(entry, bot, player);
                        markReacted(player.getId(), nowMs);
                        return;
                }
            }
        }
    }

    /* renamed from: soloMapling.ArtificialPlayer.GCMoveSystem.BotPlayerReaction$1, reason: invalid class name */
    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPlayerReaction$1.class */
    static /* synthetic */ class AnonymousClass1 {
        static final /* synthetic */ int[] $SwitchMap$org$gms$soloMapling$ArtificialPlayer$BotMovementSystem$PlayerReaction$ReactionType = new int[PlayerReaction.ReactionType.values().length];

        static {
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$BotMovementSystem$PlayerReaction$ReactionType[PlayerReaction.ReactionType.IGNORE.ordinal()] = 1;
            } catch (NoSuchFieldError e) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$BotMovementSystem$PlayerReaction$ReactionType[PlayerReaction.ReactionType.WALK_REACT.ordinal()] = 2;
            } catch (NoSuchFieldError e2) {
            }
            try {
                $SwitchMap$org$gms$soloMapling$ArtificialPlayer$BotMovementSystem$PlayerReaction$ReactionType[PlayerReaction.ReactionType.STOP_REACT.ordinal()] = 3;
            } catch (NoSuchFieldError e3) {
            }
        }
    }

    private static void reactStop(BotMovementState entry, Character bot, Character player) {
        Point pp = player.getPosition();
        Point bp = bot.getPosition();
        if (pp != null && bp != null) {
            entry.facingDir = pp.x >= bp.x ? 1 : -1;
            BotMovementManager.broadcastMovement(entry);
        }
        entry.reactingUntilMs = System.currentTimeMillis() + ThreadLocalRandom.current().nextLong(STOP_PAUSE_MIN_MS, 2501L);
        speak(bot, player);
    }

    private static void speak(Character bot, Character player) {
        BotSM botSM = CharacterStorage.getBotById(bot.getId());
        if (botSM == null) {
            PlayerReaction.executeWalkReaction(bot);
        } else {
            ExecutorServiceManager.runAsync(() -> {
                botSM.getDialogueHandler().executeBotFlavorDialogue(REACT_NODE, botSM);
            });
        }
    }

    private static boolean onCooldown(int playerId, long nowMs) {
        Long until = PLAYER_REACT_UNTIL.get(Integer.valueOf(playerId));
        if (until == null) {
            return false;
        }
        if (until.longValue() <= nowMs) {
            PLAYER_REACT_UNTIL.remove(Integer.valueOf(playerId));
            return false;
        }
        return true;
    }

    private static void markReacted(int playerId, long nowMs) {
        PLAYER_REACT_UNTIL.put(Integer.valueOf(playerId), Long.valueOf(nowMs + ThreadLocalRandom.current().nextLong(REACT_COOLDOWN_MIN_MS, 240001L)));
    }
}
