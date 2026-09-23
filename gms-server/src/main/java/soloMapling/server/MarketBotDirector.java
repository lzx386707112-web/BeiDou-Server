package soloMapling.server;

import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.BotHelpers;
import soloMapling.ArtificialPlayer.BotSM;
import soloMapling.ArtificialPlayer.BotMovementSystem.MovementCommands;
import soloMapling.FreeMarket.MarketBotLog;
import soloMapling.SoloMaplingConfig;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * One scheduler for Free Market wander/merchant bots. Avoids N per-bot
 * scheduled tasks and blocking sleeps on the shared 10-thread pool.
 */
public final class MarketBotDirector {
    private static final MarketBotDirector INSTANCE = new MarketBotDirector();

    private final ConcurrentHashMap<Integer, BotSM> bots = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, Long> nextDueAt = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Integer, Long> lastSpeechAt = new ConcurrentHashMap<>();
    private final AtomicInteger pathfindsThisTick = new AtomicInteger();
    private final ExecutorService movementExecutor = ExecutorServiceManager.getExecutorService();
    private volatile ScheduledFuture<?> loop;
    private volatile long configuredTickMs = -1;
    private volatile long lastMegaphoneAt = 0;
    private volatile long lastStatusAt = 0;

    private MarketBotDirector() {
    }

    public static MarketBotDirector get() {
        return INSTANCE;
    }

    public synchronized void register(BotSM bot, long initialDelayMs) {
        if (bot == null || bot.getChr() == null) {
            return;
        }
        int id = bot.getChr().getId();
        bots.put(id, bot);
        nextDueAt.put(id, System.currentTimeMillis() + Math.max(0, initialDelayMs));
        ensureLoop();
    }

    public void unregister(BotSM bot) {
        if (bot == null || bot.getChr() == null) {
            return;
        }
        int id = bot.getChr().getId();
        bots.remove(id);
        nextDueAt.remove(id);
    }

    public int activeCount() {
        return bots.size();
    }

    public synchronized boolean tryChat(Character chr) {
        if (chr == null || chr.getMap() == null) {
            return false;
        }
        long now = System.currentTimeMillis();
        Long last = lastSpeechAt.get(chr.getId());
        if (last != null && now - last < SoloMaplingConfig.marketSpeechGapMs()) {
            return false;
        }
        lastSpeechAt.put(chr.getId(), now);
        return true;
    }

    public synchronized boolean trySpeak(Character chr) {
        if (!SoloMaplingConfig.marketHawkEnabled()) {
            return false;
        }
        return tryChat(chr);
    }

    public synchronized boolean tryMegaphone() {
        long now = System.currentTimeMillis();
        if (now - lastMegaphoneAt < 8_000L) {
            return false;
        }
        lastMegaphoneAt = now;
        return true;
    }

    public boolean tryPathfind() {
        return pathfindsThisTick.incrementAndGet() <= SoloMaplingConfig.marketPathfindPerTick();
    }

    /**
     * Run blocking path playback off the shared director thread so ~30 market
     * bots do not stall one another while walking.
     */
    public boolean runPathfind(Runnable movement) {
        if (movement == null) {
            return false;
        }
        if (!tryPathfind()) {
            return false;
        }
        movementExecutor.execute(() -> {
            try {
                movement.run();
            } catch (Exception ignored) {
            }
        });
        return true;
    }

    public synchronized void refreshTickInterval() {
        long tickMs = SoloMaplingConfig.marketTickMs();
        if (loop != null && configuredTickMs == tickMs) {
            return;
        }
        if (loop != null) {
            loop.cancel(false);
            loop = null;
        }
        configuredTickMs = tickMs;
        if (!bots.isEmpty()) {
            ensureLoop();
        }
    }

    private void ensureLoop() {
        long tickMs = SoloMaplingConfig.marketTickMs();
        if (loop != null && !loop.isCancelled() && configuredTickMs == tickMs) {
            return;
        }
        if (loop != null) {
            loop.cancel(false);
        }
        configuredTickMs = tickMs;
        loop = ExecutorServiceManager.getScheduledExecutorService().scheduleWithFixedDelay(
                this::tick, tickMs, tickMs, TimeUnit.MILLISECONDS);
    }

    private void tick() {
        pathfindsThisTick.set(0);
        long now = System.currentTimeMillis();
        List<BotSM> snapshot = new ArrayList<>(bots.values());
        if (now - lastStatusAt > 20_000L) {
            lastStatusAt = now;
            int sitting = 0;
            int moving = 0;
            for (BotSM bot : snapshot) {
                Character chr = bot.getChr();
                if (chr == null) {
                    continue;
                }
                if (chr.getChair() > 0) {
                    sitting++;
                }
                if (MovementCommands.isBotMoving(chr)) {
                    moving++;
                }
            }
            // BOTLOG-MUTE: MarketBotLog.info("market status bots={} moving={} sitting={} idle={}",
                    // BOTLOG-MUTE: snapshot.size(), moving, sitting, Math.max(0, snapshot.size() - moving - sitting));
        }
        Map<Integer, Boolean> playersByMap = new HashMap<>();
        for (BotSM bot : snapshot) {
            Character chr = bot.getChr();
            if (chr == null || chr.getMap() == null) {
                continue;
            }
            int mapId = chr.getMapId();
            playersByMap.computeIfAbsent(mapId, ignored -> mapHasRealPlayer(chr.getMap()));
        }

        for (BotSM bot : snapshot) {
            Character chr = bot.getChr();
            if (chr == null) {
                continue;
            }
            int id = chr.getId();
            Long due = nextDueAt.get(id);
            if (due != null && now < due) {
                continue;
            }
            if (chr.getTrade() == null && MovementCommands.isBotMoving(chr)) {
                continue;
            }
            boolean playersHere = playersByMap.getOrDefault(chr.getMapId(), true);
            if (SoloMaplingConfig.marketIdleWhenEmpty() && !playersHere) {
                nextDueAt.put(id, now + 8_000L + ThreadLocalRandom.current().nextInt(4_000));
                continue;
            }
            try {
                bot.updateState();
            } catch (Exception e) {
                // BOTLOG-MUTE: MarketBotLog.error("Market bot tick failed name=" + (chr.getName()) + " map=" + chr.getMapId(), e);
            }
            long pause = playersHere
                    ? 800L + ThreadLocalRandom.current().nextInt(1200)
                    : 4_000L + ThreadLocalRandom.current().nextInt(3_000);
            nextDueAt.put(id, System.currentTimeMillis() + pause);
        }
    }

    private static boolean mapHasRealPlayer(MapleMap map) {
        for (Character chr : map.getCharacters()) {
            if (!BotHelpers.isBot(chr)) {
                return true;
            }
        }
        return false;
    }
}
