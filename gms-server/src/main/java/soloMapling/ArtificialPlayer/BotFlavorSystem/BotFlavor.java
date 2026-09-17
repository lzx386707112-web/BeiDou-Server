package soloMapling.ArtificialPlayer.BotFlavorSystem;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import org.gms.client.Character;
import soloMapling.ArtificialPlayer.BotCommandsPack.BotAttack;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

public final class BotFlavor {
    public static volatile double FLAVOR_CHANCE = 0.12d;
    public static volatile long FLAVOR_COOLDOWN_MIN_MS = 15000;
    public static volatile long FLAVOR_COOLDOWN_MAX_MS = 40000;
    private static final int[] FRIENDLY_EMOTES = {1, 2, 5, 6};
    private static final Map<Integer, Long> cooldownUntil = new ConcurrentHashMap<>();

    private BotFlavor() {
    }

    public static void maybeExpress(BotSM bot) {
        Character chr;
        if (bot == null || (chr = bot.getChr()) == null || chr.getMap() == null
                || bot.getState() == BotSM.BotState.TRADING
                || !bot.checkMainPlayersOnMap()) {
            return;
        }
        long now = System.currentTimeMillis();
        Long until = cooldownUntil.get(chr.getId());
        if ((until != null && now < until) || ThreadLocalRandom.current().nextDouble() >= FLAVOR_CHANCE) {
            return;
        }
        dispatch(chr, pickAction());
        long span = Math.max(1L, FLAVOR_COOLDOWN_MAX_MS - FLAVOR_COOLDOWN_MIN_MS);
        long cd = FLAVOR_COOLDOWN_MIN_MS + (long) (ThreadLocalRandom.current().nextDouble() * span);
        cooldownUntil.put(chr.getId(), now + cd);
    }

    public static void forget(Character chr) {
        if (chr != null) {
            cooldownUntil.remove(chr.getId());
        }
    }

    public static void forceExpress(BotSM bot) {
        forceExpress(bot, pickAction());
    }

    public static void forceExpress(BotSM bot, FlavorAction action) {
        Character chr;
        if (bot == null || action == null || (chr = bot.getChr()) == null || chr.getMap() == null) {
            return;
        }
        dispatch(chr, action);
    }

    private static FlavorAction pickAction() {
        int total = 0;
        for (FlavorAction flavorAction : FlavorAction.values()) {
            total += flavorAction.weight;
        }
        int roll = ThreadLocalRandom.current().nextInt(total);
        for (FlavorAction a : FlavorAction.values()) {
            roll -= a.weight;
            if (roll < 0) {
                return a;
            }
        }
        return FlavorAction.EMOTE;
    }

    private static void dispatch(Character chr, FlavorAction action) {
        switch (action) {
            case EMOTE, BUFF_FLEX -> doEmote(chr);
            case SKILL_SWING -> doSkillSwing(chr);
        }
    }

    private static void doEmote(Character chr) {
        int id = FRIENDLY_EMOTES[ThreadLocalRandom.current().nextInt(FRIENDLY_EMOTES.length)];
        SocialCommands.BotEmote(chr, id);
    }

    private static void doSkillSwing(Character chr) {
        GCMovement.markAlerted(chr);
        BotAttack.basicSwing(chr);
    }
}
