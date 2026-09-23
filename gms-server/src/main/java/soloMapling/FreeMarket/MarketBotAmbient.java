package soloMapling.FreeMarket;

import org.gms.client.Character;
import org.gms.client.Mount;
import org.gms.constants.skills.Beginner;
import org.gms.util.PacketCreator;
import soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.Environment.Platform;
import soloMapling.Environment.PlatformParser;
import soloMapling.Environment.PlatformSpawner;
import soloMapling.SoloMaplingConfig;
import soloMapling.server.MarketBotDirector;

import java.awt.Point;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;

import static soloMapling.ArtificialPlayer.BotCommandsPack.SocialCommands.BotEmote;
import static soloMapling.ArtificialPlayer.BotCustomization.getRandomChairId;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botCancelChair;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botJump;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.botSitChair;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.isBotMoving;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.microTurnAround;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.pathFinderBeta;
import static soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands.walkAlongX;
import static soloMapling.Environment.EnvironmentManager.getCurrentPlatform;
import static soloMapling.Environment.EnvironmentManager.getMainPlatformIds;

/**
 * Shared market-bot life: every registered dummy walks, pauses, sits, talks.
 * Sitting dummies only speak. Walking is a short stroll then a real rest, not a treadmill.
 */
public final class MarketBotAmbient {
    private static final int STROLL_STEPS = 18;
    private static final int FM_ENTRANCE = 910000000;
    static final int[][] MOUNT_PAIRS = {
            {1902000, 1912000},
            {1902001, 1912000},
            {1902002, 1912000},
            {1902005, 1912005},
            {1902008, 1912003},
            {1902009, 1912004},
            {1902011, 1912007},
            {1902012, 1912008}
    };

    private enum Phase {
        REST,
        WALK,
        SIT,
        CLIMB
    }

    private static final class Life {
        private Phase phase = Phase.REST;
        private long phaseUntil;
        private final int sitBias;
        private int strollDir;

        private Life(ThreadLocalRandom rng) {
            this.sitBias = rng.nextInt(8, 14);
            this.strollDir = rng.nextBoolean() ? 1 : -1;
            this.phaseUntil = System.currentTimeMillis() + rng.nextInt(400, 1600);
        }
    }

    private static final ConcurrentHashMap<Integer, Life> LIVES = new ConcurrentHashMap<>();

    private MarketBotAmbient() {
    }

    public static boolean isSitting(Character chr) {
        return chr != null && chr.getChair() > 0;
    }

    public static void act(BotSM bot) {
        if (bot == null || bot.getChr() == null || bot.getChr().getMap() == null) {
            return;
        }
        Character chr = bot.getChr();
        if (chr.getTrade() != null) {
            return;
        }
        if (isBotMoving(chr)) {
            return;
        }

        Life life = LIVES.computeIfAbsent(chr.getId(), ignored -> new Life(ThreadLocalRandom.current()));
        long now = System.currentTimeMillis();
        ThreadLocalRandom rng = ThreadLocalRandom.current();

        if (keepsShopChair(chr)) {
            if (chr.getChair() <= 0) {
                sitDown(chr);
            }
            talkWhileSitting(chr);
            return;
        }

        if (life.phase == Phase.SIT && chr.getChair() > 0 && now < life.phaseUntil) {
            talkWhileSitting(chr);
            return;
        }

        if (life.phase == Phase.SIT && (chr.getChair() <= 0 || now >= life.phaseUntil)) {
            standUp(chr);
            enterRest(life, rng, 2500, 7000);
            fidget(chr, rng);
            return;
        }

        if (life.phase == Phase.REST && now < life.phaseUntil) {
            fidget(chr, rng);
            return;
        }
        if ((life.phase == Phase.WALK || life.phase == Phase.CLIMB) && now < life.phaseUntil) {
            return;
        }

        if (!SoloMaplingConfig.marketWanderEnabled()) {
            talkWhileIdle(chr);
            return;
        }

        pickNextAction(bot, life, rng);
    }

    private static void pickNextAction(BotSM bot, Life life, ThreadLocalRandom rng) {
        Character chr = bot.getChr();
        int roll = rng.nextInt(100);
        if (roll < 72) {
            startStroll(bot, life, rng, false);
        } else if (roll < 72 + life.sitBias) {
            startSit(chr, life, rng);
        } else if (roll < 86 && chr.getMapId() == FM_ENTRANCE) {
            startClimb(bot, life);
        } else if (roll < 93) {
            startStroll(bot, life, rng, true);
        } else if (roll < 97) {
            rideMount(chr);
            startStroll(bot, life, rng, false);
        } else {
            talkWhileIdle(chr);
            enterRest(life, rng, 800, 2200);
        }
    }

    private static void startStroll(BotSM bot, Life life, ThreadLocalRandom rng, boolean jumpFirst) {
        Character chr = bot.getChr();
        if (chr.getChair() > 0) {
            standUp(chr);
        }
        Platform platform = currentPlatform(chr);
        Point here = chr.getPosition();
        Point dest = strollTarget(platform, here.x, life.strollDir, rng);
        life.strollDir = dest.x >= here.x ? 1 : -1;
        Point destGround = PlatformSpawner.snapToGround(chr.getMap(), new Point(dest.x, here.y));
        if (destGround != null) {
            dest = destGround;
        } else {
            dest.y = here.y;
        }
        life.phase = Phase.WALK;
        life.phaseUntil = System.currentTimeMillis() + 8000;
        // BOTLOG-MUTE: MarketBotLog.debug("stroll name={} map={} fromX={} toX={} jump={}",
                // BOTLOG-MUTE: chr.getName(), chr.getMapId(), here.x, dest.x, jumpFirst);
        Point walkTo = dest;
        MarketBotDirector.get().runPathfind(() -> {
            if (jumpFirst) {
                botJump(chr);
            }
            walkAlongX(chr, walkTo, STROLL_STEPS);
            enterRest(life, ThreadLocalRandom.current(), 900, 2800);
        });
    }

    private static void startClimb(BotSM bot, Life life) {
        Character chr = bot.getChr();
        if (chr.getChair() > 0) {
            standUp(chr);
        }
        Point dest = otherFloorTarget(chr);
        if (dest == null) {
            startStroll(bot, life, ThreadLocalRandom.current(), false);
            return;
        }
        life.phase = Phase.CLIMB;
        life.phaseUntil = System.currentTimeMillis() + 16_000;
        MarketBotDirector.get().runPathfind(() -> {
            pathFinderBeta(chr, dest);
            enterRest(life, ThreadLocalRandom.current(), 1800, 4500);
        });
    }

    private static void startSit(Character chr, Life life, ThreadLocalRandom rng) {
        sitDown(chr);
        life.phase = Phase.SIT;
        life.phaseUntil = System.currentTimeMillis() + rng.nextInt(12_000, 28_000);
    }

    private static void sitDown(Character chr) {
        if (chr.getChair() > 0) {
            return;
        }
        botSitChair(chr, getRandomChairId());
    }

    private static void standUp(Character chr) {
        if (chr.getChair() > 0) {
            botCancelChair(chr);
        }
    }

    private static void enterRest(Life life, ThreadLocalRandom rng, int minMs, int maxMs) {
        life.phase = Phase.REST;
        life.phaseUntil = System.currentTimeMillis() + rng.nextInt(minMs, maxMs);
    }

    private static boolean keepsShopChair(Character chr) {
        return chr.getPlayerShop() != null && chr.getPlayerShop().isOpen();
    }

    private static void fidget(Character chr, ThreadLocalRandom rng) {
        int roll = rng.nextInt(100);
        if (roll < 18) {
            talkWhileIdle(chr);
        } else if (roll < 28) {
            BotEmote(chr);
        } else if (roll < 36) {
            microTurnAround(chr);
        }
    }

    private static void talkWhileSitting(Character chr) {
        if (ThreadLocalRandom.current().nextInt(100) >= 28) {
            return;
        }
        if (MarketBotDirector.get().tryChat(chr)) {
            SocialCommands.BotSpeak(chr, MarketBotFlavor.chat());
        }
    }

    private static void talkWhileIdle(Character chr) {
        Character other = nearbyBot(chr, 220);
        if (other != null && MarketBotDirector.get().tryChat(chr)) {
            SocialCommands.BotSpeak(chr, MarketBotFlavor.chat());
            if (MarketBotDirector.get().tryChat(other)) {
                SocialCommands.BotSpeak(other, MarketBotFlavor.reply());
            }
            return;
        }
        if (MarketBotDirector.get().tryChat(chr)) {
            SocialCommands.BotSpeak(chr, MarketBotFlavor.chat());
        }
    }

    static void rideMount(Character chr) {
        if (chr == null || chr.getMap() == null || chr.getChair() > 0) {
            return;
        }
        int[] pair = MOUNT_PAIRS[ThreadLocalRandom.current().nextInt(MOUNT_PAIRS.length)];
        Mount mount = chr.mount(pair[0], Beginner.MONSTER_RIDER);
        mount.setActive(true);
        chr.getMap().broadcastMessage(PacketCreator.showMonsterRiding(chr.getId(), mount));
    }

    static Point otherFloorTarget(Character chr) {
        List<String> ids = getMainPlatformIds(chr.getMapId());
        if (ids == null || ids.size() < 2) {
            return null;
        }
        String current = getCurrentPlatform(chr);
        List<String> others = new ArrayList<>();
        for (String id : ids) {
            if (id != null && !id.equals(current)) {
                others.add(id);
            }
        }
        if (others.isEmpty()) {
            others.addAll(ids);
        }
        String pick = others.get(ThreadLocalRandom.current().nextInt(others.size()));
        try {
            Platform platform = PlatformParser.parsePlatform(chr.getMapId(), pick);
            int x = platform.getMinX() + 40 + ThreadLocalRandom.current().nextInt(Math.max(1, platform.getWidth() - 80));
            return new Point(x, platform.getYAtX(x));
        } catch (Exception ignored) {
            return null;
        }
    }

    static Point strollTarget(Platform platform, int currentX, int preferredDir, ThreadLocalRandom rng) {
        int distance = 120 + rng.nextInt(161);
        int dir = preferredDir >= 0 ? 1 : -1;
        if (platform == null) {
            return new Point(currentX + dir * distance, 0);
        }
        int min = platform.getMinX() + 24;
        int max = platform.getMaxX() - 24;
        if (max <= min) {
            return new Point(currentX, platform.getYAtX(currentX));
        }
        if (currentX + dir * distance > max || currentX + dir * distance < min) {
            dir = -dir;
        }
        int destX = Math.max(min, Math.min(max, currentX + dir * distance));
        return new Point(destX, platform.getYAtX(destX));
    }

    static Point patrolTarget(Platform platform, int currentX, ThreadLocalRandom rng) {
        return strollTarget(platform, currentX, rng.nextBoolean() ? 1 : -1, rng);
    }

    private static Platform currentPlatform(Character chr) {
        String id = getCurrentPlatform(chr);
        if (id == null || id.isBlank()) {
            List<String> ids = getMainPlatformIds(chr.getMapId());
            if (ids != null && !ids.isEmpty()) {
                id = ids.get(0);
            } else {
                id = "m1";
            }
        }
        try {
            return PlatformParser.parsePlatform(chr.getMapId(), id);
        } catch (Exception ignored) {
            return null;
        }
    }

    private static Character nearbyBot(Character chr, int range) {
        List<Character> bots = new ArrayList<>();
        for (Character other : chr.getMap().getAllPlayers()) {
            if (other == null || other.getId() == chr.getId() || !BotHelpers.isBot(other)) {
                continue;
            }
            if (Math.abs(other.getPosition().x - chr.getPosition().x) <= range
                    && Math.abs(other.getPosition().y - chr.getPosition().y) <= 80) {
                bots.add(other);
            }
        }
        if (bots.isEmpty()) {
            return null;
        }
        return bots.get(ThreadLocalRandom.current().nextInt(bots.size()));
    }
}
