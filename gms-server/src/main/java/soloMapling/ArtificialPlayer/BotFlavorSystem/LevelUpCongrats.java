package soloMapling.ArtificialPlayer.BotFlavorSystem;

import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotDialogueHandler;
import soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;
import soloMapling.server.BotTiming;
import soloMapling.server.EventMessageSystem.EventType;
import soloMapling.server.EventMessageSystem.GameEvent;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotFlavorSystem/LevelUpCongrats.class */
public final class LevelUpCongrats {
    private static final String NODE = "CongratsLevelUp";
    public static volatile double CONGRATS_CHANCE = 0.3d;
    public static volatile int CONGRATS_RADIUS = 350;
    public static volatile long CONGRATS_DELAY_MIN_MS = 5000;
    public static volatile long CONGRATS_DELAY_MAX_MS = 9000;
    private static final int[] CONGRATS_EMOTES = {2, 6};

    private LevelUpCongrats() {
    }

    public static void react(BotSM bot, GameEvent event) {
        if (bot == null || event == null || event.getType() != EventType.LEVEL_UP) {
            return;
        }
        Character me = bot.getChr();
        Character leveler = event.getMapleCharacter();
        if (me == null || me.getMap() == null || leveler == null || leveler.getId() == me.getId() || !bot.isAvailableForAmbientActions() || leveler.getMap() != me.getMap()) {
            return;
        }
        double radius = CONGRATS_RADIUS;
        if (me.getPosition().distanceSq(leveler.getPosition()) > radius * radius || ThreadLocalRandom.current().nextDouble() >= CONGRATS_CHANCE) {
            return;
        }
        BotTiming.afterRandom(CONGRATS_DELAY_MIN_MS, CONGRATS_DELAY_MAX_MS, () -> {
            fire(bot, leveler);
        });
    }

    /* JADX INFO: Access modifiers changed from: private */
    public static void fire(BotSM bot, Character leveler) {
        String line;
        Character me = bot.getChr();
        if (me == null || me.getMap() == null || leveler == null || !bot.isAvailableForAmbientActions() || leveler.getMap() != me.getMap()) {
            return;
        }
        try {
            line = BotDialogueHandler.getRandomDialogueLine(bot, NODE);
        } catch (Exception e) {
            line = null;
        }
        String spoken = line;
        int emote = CONGRATS_EMOTES[ThreadLocalRandom.current().nextInt(CONGRATS_EMOTES.length)];
        BotTiming.chain().stopUnless(() -> {
            return bot.isAvailableForAmbientActions() && leveler.getMap() == me.getMap();
        }).run(() -> {
            MovementCommands.botFaceTowardsPoint(me, leveler.getPosition());
        }).pauseRandom(300L, 700L).run(() -> {
            if (spoken != null) {
                SocialCommands.BotSpeak(me, spoken);
            }
        }).pause(400L).run(() -> {
            SocialCommands.BotEmote(me, emote);
        }).start();
    }
}
